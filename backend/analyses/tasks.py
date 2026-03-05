"""LLM 분석 태스크"""

import logging
import re
from difflib import SequenceMatcher

from articles.models import Article
from django.conf import settings
from django.db.models import Count, Q

from analyses.models import Analysis, CaseGroup
from analyses.prompts import build_messages
from analyses.validators import validate_and_parse

logger = logging.getLogger(__name__)

# 유사도 매칭 임계값 — 낮을수록 다른 사건이 합쳐지는 false positive 증가
CASE_SIMILARITY_THRESHOLD = 0.85


class DailyQuotaExceededError(Exception):
    """Gemini 일일 요청 한도 초과 — 다음 날 자정(UTC) 이후 초기화"""
    pass


def _is_any_quota_error(e: Exception) -> bool:
    """429 rate limit 에러 감지 (일일 한도 및 분당 한도 모두 포함)"""
    return "RESOURCE_EXHAUSTED" in str(e)


# ---------------------------------------------------------------------------
# 프로세스 간 공유 quota 상태 (파일 캐시 → CLI/스케줄러 모두 읽기·쓰기 가능)
# ---------------------------------------------------------------------------
_QUOTA_CACHE_KEY = "gemini_quota_error"
_QUOTA_CACHE_TTL = 60 * 60 * 24  # 24시간


def set_quota_error(msg: str) -> None:
    from django.core.cache import cache
    cache.set(_QUOTA_CACHE_KEY, msg, timeout=_QUOTA_CACHE_TTL)


def clear_quota_error() -> None:
    from django.core.cache import cache
    cache.delete(_QUOTA_CACHE_KEY)


def get_quota_error() -> str | None:
    from django.core.cache import cache
    return cache.get(_QUOTA_CACHE_KEY)

# 제목 키워드 기반 그룹 매칭 — 공유 키워드 N개 이상이면 같은 사건 그룹으로 판단
# 낮을수록 동일 토픽의 다른 사건이 합쳐질 위험 증가
TITLE_KEYWORD_MATCH_COUNT = 5

# 사건명에서 자주 등장하는 일반 법률/분류 용어 (유사도 매칭 시 제외)
_CASE_STOPWORDS = {
    "소송",
    "분쟁",
    "사건",
    "피해",
    "소비자",
    "유출",
    "논란",
    "문제",
    "관련",
    "사태",
    "조사",
    "처리",
    "대응",
    "보상",
    "청구",
    "재판",
    "판결",
    "기소",
    "수사",
    "검찰",
    "경찰",
    "법원",
    "소송중",
    "민원",
    "접수",
    "안내",
    "경고",
    "주의",
    "예방",
    "위반",
    "혐의",
    "의혹",
    "인상",
    "인하",
    "확대",
    "축소",
    "폭리",
    "피싱",
    "스미싱",
    # 기사 제목에서 그룹핑에 의미 없는 추가 단어
    "기자",
    "뉴스",
    "보도",
    "취재",
    "단독",
    "속보",
    "긴급",
    "확인",
    "발표",
    "주장",
    "강조",
    "밝혀",
    "지적",
    "제기",
    "요구",
    "촉구",
    "개선",
    "추진",
    "계획",
    "예정",
    "전망",
    "분석",
    "공개",
    "제도",
}


def parse_damage_amount(text: str) -> int | None:
    """
    피해 규모 텍스트를 원(KRW) 단위 정수로 파싱.
    파싱 불가(미상, 빈값 등)이면 None 반환.

    예시:
      "약 500억원"    → 50_000_000_000
      "1,200만원"     → 12_000_000
      "2조 3천억원"   → 2_300_000_000_000
      "수백억 원대"   → 30_000_000_000  (보수적 추정값)
      "수조 원대"     → 3_000_000_000_000
      "미상"          → None
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    # 미상 / 불명 / 알 수 없음 등
    if re.search(r"미상|불명|알\s*수\s*없|불확실|확인\s*안\s*됨|확인\s*불가", text):
        return None

    try:
        # 쉼표, 공백 정규화
        t = re.sub(r",", "", text)

        # 한자어 수사 단독 처리 (숫자 없이 "수조", "수백억" 등)
        if not re.search(r"\d", t):
            if re.search(r"수\s*조", t):
                return 3_000_000_000_000    # 수조 ≈ 3조
            if re.search(r"수\s*천\s*억", t):
                return 300_000_000_000      # 수천억 ≈ 3000억
            if re.search(r"수\s*백\s*억", t):
                return 30_000_000_000       # 수백억 ≈ 300억
            if re.search(r"수\s*십\s*억", t):
                return 5_000_000_000        # 수십억 ≈ 50억
            if re.search(r"수\s*억", t):
                return 500_000_000          # 수억 ≈ 5억
            if re.search(r"수\s*천\s*만", t):
                return 30_000_000           # 수천만 ≈ 3000만
            if re.search(r"수\s*백\s*만", t):
                return 3_000_000            # 수백만 ≈ 300만
            return None

        total = 0

        # 조 단위 (1조 = 1,000,000,000,000원)
        m = re.search(r"([\d.]+)\s*조", t)
        if m:
            total += int(float(m.group(1)) * 1_000_000_000_000)

        # 억 단위 (1억 = 100,000,000원)
        m = re.search(r"([\d.]+)\s*억", t)
        if m:
            total += int(float(m.group(1)) * 100_000_000)

        # 천 단위 (1천 = 1,000원, 단독으로 쓰인 경우 — 억/조 없을 때)
        m = re.search(r"([\d.]+)\s*천\s*(?:만|원)", t)
        if m:
            unit = 10_000 if "만" in t[m.end() - 1 : m.end() + 1] else 1_000
            total += int(float(m.group(1)) * unit)

        # 만 단위 (1만 = 10,000원)
        m = re.search(r"([\d.]+)\s*만", t)
        if m:
            total += int(float(m.group(1)) * 10_000)

        # 순수 원 단위 (억/만 단위가 없고 숫자+원만 있는 경우)
        if total == 0:
            m = re.search(r"([\d.]+)\s*원", t)
            if m:
                total += int(float(m.group(1)))

        return total if total > 0 else None

    except (ValueError, OverflowError):
        return None


def parse_victim_count(text: str) -> int | None:
    """
    피해자 수 텍스트를 정수로 파싱.
    파싱 불가(미상, 빈값 등)이면 None 반환.

    예시:
      "약 1만 2천명"  → 12_000
      "50명 이상"     → 50
      "약 3만명"      → 30_000
      "미상"          → None
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    if re.search(r"미상|불명|알\s*수\s*없|불확실|확인\s*안\s*됨|확인\s*불가", text):
        return None

    try:
        t = re.sub(r",", "", text)

        total = 0

        # 한자어 수사 단독 처리 (숫자 없이 "수만", "수십만" 등)
        # 수십만 > 수만 > 수천 > 수백 순으로 체크
        if re.search(r"수\s*십\s*만", t):
            return 200_000   # 수십만 ≈ 200,000 (보수적 하한)
        if re.search(r"수\s*만", t) and not re.search(r"\d", t):
            return 30_000    # 수만 ≈ 30,000
        if re.search(r"수\s*천", t) and not re.search(r"\d", t):
            return 3_000     # 수천 ≈ 3,000
        if re.search(r"수\s*백", t) and not re.search(r"\d", t):
            return 300       # 수백 ≈ 300

        if not re.search(r"\d", t):
            return None

        # 만 단위
        m = re.search(r"([\d.]+)\s*만", t)
        if m:
            total += int(float(m.group(1)) * 10_000)

        # 천 단위
        m = re.search(r"([\d.]+)\s*천", t)
        if m:
            total += int(float(m.group(1)) * 1_000)

        # 백 단위
        m = re.search(r"([\d.]+)\s*백", t)
        if m:
            total += int(float(m.group(1)) * 100)

        # 순수 숫자 (만/천 단위 없을 때)
        if total == 0:
            m = re.search(r"(\d+)", t)
            if m:
                total += int(m.group(1))

        return total if total > 0 else None

    except (ValueError, OverflowError):
        return None


def call_gemini(messages: list[dict]) -> tuple[str, int, int]:
    """Gemini API 호출 (기본 LLM) — google-genai SDK"""
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt_parts = []
    for msg in messages:
        prompt_parts.append(f"[{msg['role']}]: {msg['content']}")

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents="\n\n".join(prompt_parts),
        config={
            "temperature": settings.LLM_TEMPERATURE,
            "max_output_tokens": settings.LLM_MAX_TOKENS,
            "response_mime_type": "application/json",
        },
    )
    usage = response.usage_metadata
    return (
        response.text,
        (usage.prompt_token_count or 0) if usage else 0,
        (usage.candidates_token_count or 0) if usage else 0,
    )


def get_existing_case_names() -> list[str]:
    """활성 사건 그룹 이름 목록 조회.

    범위: is_relevant 기사가 있는 그룹 중 최근 90일 내 기사가 있는 그룹 우선,
    최대 150개 (LLM 컨텍스트 과부하 방지).
    """
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=90)
    groups = (
        CaseGroup.objects.annotate(
            relevant_count=Count("analyses", filter=Q(analyses__is_relevant=True)),
            recent_count=Count(
                "analyses",
                filter=Q(
                    analyses__is_relevant=True,
                    analyses__article__published_at__gte=cutoff,
                ),
            ),
        )
        .filter(relevant_count__gt=0)
        .order_by("-recent_count", "-relevant_count")
        .values_list("name", flat=True)[:150]
    )
    return list(groups)


def _case_similarity(a: str, b: str) -> float:
    """핵심 엔티티 기반 사건명 유사도 (stopword 제외)"""
    seq_ratio = SequenceMatcher(None, a, b).ratio()

    # 의미있는 토큰 추출 (stopword 제외, 2자 이상)
    tokens_a = {t for t in a.split() if len(t) >= 2 and t not in _CASE_STOPWORDS}
    tokens_b = {t for t in b.split() if len(t) >= 2 and t not in _CASE_STOPWORDS}

    # 핵심 토큰(엔티티) 공유 여부
    shared = tokens_a & tokens_b
    if shared:
        bonus = min(len(shared) * 0.25, 0.5)
        return min(seq_ratio + bonus, 1.0)

    # 부분 문자열 매칭: 핵심 엔티티(3자 이상)가 상대 문자열에 포함?
    for t in tokens_a:
        if len(t) >= 3 and t in b:
            return min(seq_ratio + 0.25, 1.0)
    for t in tokens_b:
        if len(t) >= 3 and t in a:
            return min(seq_ratio + 0.25, 1.0)

    return seq_ratio


def _extract_title_keywords(text: str) -> set[str]:
    """기사 제목에서 유의미한 키워드 추출 (한글 2자 이상, stopword 제외)"""
    words = re.findall(r"[가-힣]{2,}", text)
    return {w for w in words if w not in _CASE_STOPWORDS}


def find_or_create_case_group(
    case_name: str, article_title: str = "", article_date=None
) -> CaseGroup | None:
    """사건명으로 기존 CaseGroup을 찾거나 유사도 매칭 후 새로 생성.

    매칭 순서:
      1) case_name 정확 일치
      2) case_name 유사도 매칭 (SequenceMatcher + 토큰 보너스)
      3) 기사 제목 키워드 겹침 매칭 (case_name 매칭 실패 시 fallback)
         — 최근 30일 기사 제목과 TITLE_KEYWORD_MATCH_COUNT개 이상 공유 시 같은 그룹
      4) 새 그룹 생성
    """
    if not case_name:
        if not article_title:
            return None
        case_name = article_title[:80]

    # 1) 정확히 일치하는 그룹
    existing = CaseGroup.objects.filter(name=case_name).first()
    if existing:
        return existing

    # id, name만 로드 (full object 불필요 — 이후 단계에서 재사용)
    all_groups = list(CaseGroup.objects.values("id", "name"))

    # 2) case_name 유사도 매칭
    best_match_id = None
    best_match_name = None
    best_ratio = 0.0
    for group in all_groups:
        ratio = _case_similarity(case_name, group["name"])
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_id = group["id"]
            best_match_name = group["name"]

    if best_match_id and best_ratio >= CASE_SIMILARITY_THRESHOLD:
        logger.info(
            "사건 그룹 유사도 매칭: '%s' → '%s' (%.2f)",
            case_name,
            best_match_name,
            best_ratio,
        )
        return CaseGroup.objects.get(id=best_match_id)

    # 3) 기사 제목 키워드 겹침 매칭 (fallback)
    #    같은 사건을 다른 언론사가 다른 각도로 보도할 때
    #    LLM이 다른 case_name을 부여해도 제목 키워드로 묶어줌
    if article_title and all_groups:
        from datetime import timedelta

        from django.utils import timezone

        recent_cutoff = timezone.now() - timedelta(days=30)
        title_keywords = _extract_title_keywords(article_title)

        if len(title_keywords) >= TITLE_KEYWORD_MATCH_COUNT:
            # 그룹별 최근 기사 제목을 한 쿼리로 가져옴
            from django.db.models import OuterRef, Subquery

            latest_titles = (
                Analysis.objects.filter(
                    case_group=OuterRef("pk"),
                    article__published_at__gte=recent_cutoff,
                )
                .order_by("-article__published_at")
                .values("article__title")[:1]
            )
            groups_with_titles = (
                CaseGroup.objects.annotate(latest_title=Subquery(latest_titles))
                .values("id", "name", "latest_title")
            )

            best_kw_match = None
            best_kw_count = 0
            for g in groups_with_titles:
                if not g["latest_title"]:
                    continue
                group_keywords = _extract_title_keywords(g["latest_title"])
                shared = title_keywords & group_keywords
                if len(shared) > best_kw_count:
                    best_kw_count = len(shared)
                    best_kw_match = g

            if best_kw_match and best_kw_count >= TITLE_KEYWORD_MATCH_COUNT:
                group_obj = CaseGroup.objects.get(id=best_kw_match["id"])
                logger.info(
                    "기사 제목 키워드 매칭: '%s' → '%s' (공유키워드 %d개: %s)",
                    article_title[:50],
                    best_kw_match["name"],
                    best_kw_count,
                    ", ".join(
                        title_keywords
                        & _extract_title_keywords(best_kw_match["latest_title"])
                    ),
                )
                return group_obj

    # 4) 새 그룹 생성
    case_id = CaseGroup.generate_next_case_id(article_date=article_date)
    return CaseGroup.objects.create(case_id=case_id, name=case_name)


def analyze_single_article(article: Article) -> bool:
    """단일 기사 분석 → 성공 여부 반환"""
    if Analysis.objects.filter(article=article).exists():
        article.status = "analyzed"
        article.save(update_fields=["status"])
        return True

    article.status = "analyzing"
    article.save(update_fields=["status"])

    # 기존 사건 그룹 목록을 프롬프트에 주입
    existing_case_names = get_existing_case_names()
    messages = build_messages(article.title, article.content, existing_case_names)

    if not getattr(settings, "GEMINI_API_KEY", ""):
        logger.error("GEMINI_API_KEY가 설정되지 않음")
        article.status = "failed"
        article.retry_count += 1
        article.save(update_fields=["status", "retry_count"])
        return False

    try:
        raw_response, prompt_tokens, completion_tokens = call_gemini(messages)
    except Exception as e:
        if _is_any_quota_error(e):
            article.status = "pending"
            article.save(update_fields=["status"])
            raise DailyQuotaExceededError(str(e)) from e
        logger.exception("Gemini API 호출 실패: article=%d", article.pk)
        article.status = "failed"
        article.retry_count += 1
        article.save(update_fields=["status", "retry_count"])
        return False

    parsed = validate_and_parse(raw_response)
    if not parsed:
        article.status = "failed"
        article.retry_count += 1
        article.save(update_fields=["status", "retry_count"])
        return False

    # 사건 그룹 연결
    case_group = find_or_create_case_group(
        parsed.get("case_name", ""),
        article_title=article.title,
        article_date=article.published_at.date(),
    )

    damage_amount_text = parsed.get("damage_amount", "미상")
    victim_count_text = parsed.get("victim_count", "미상")

    Analysis.objects.update_or_create(
        article=article,
        defaults=dict(
            case_group=case_group,
            suitability=parsed["suitability"],
            suitability_reason=parsed["suitability_reason"],
            case_category=parsed["case_category"],
            defendant=parsed.get("defendant", ""),
            damage_amount=damage_amount_text,
            damage_amount_num=parse_damage_amount(damage_amount_text),
            victim_count=victim_count_text,
            victim_count_num=parse_victim_count(victim_count_text),
            stage=parsed.get("stage", ""),
            stage_detail=parsed.get("stage_detail", ""),
            summary=parsed["summary"],
            is_relevant=parsed.get("is_relevant", True),
            llm_model=settings.GEMINI_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )

    article.status = "analyzed"
    article.save(update_fields=["status"])
    return True


def analyze_pending_articles():
    """분석 대기(pending/analyzing) 상태의 기사를 일괄 분석"""
    pending = Article.objects.filter(status__in=["pending", "analyzing"]).order_by(
        "collected_at"
    )
    total = pending.count()
    success = 0
    failed = 0

    for article in pending:
        if analyze_single_article(article):
            success += 1
        else:
            failed += 1

    logger.info("분석 완료: 전체 %d건, 성공 %d, 실패 %d", total, success, failed)
    return {"total": total, "success": success, "failed": failed}


def reanalyze_article(article_id: int):
    """특정 기사 재분석"""
    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        logger.error("기사를 찾을 수 없음: %d", article_id)
        return False

    # 기존 분석 결과 삭제
    Analysis.objects.filter(article=article).delete()
    article.status = "pending"
    article.save(update_fields=["status"])

    return analyze_single_article(article)
