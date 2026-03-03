"""LLM 분석 Celery 태스크"""

import logging
import re
from difflib import SequenceMatcher

from celery import shared_task
from django.conf import settings
from django.db.models import Count, Q

from analyses.models import Analysis, CaseGroup
from analyses.prompts import build_messages
from analyses.validators import validate_and_parse
from articles.models import Article

logger = logging.getLogger(__name__)

# 유사도 매칭 임계값
CASE_SIMILARITY_THRESHOLD = 0.6

# 제목 키워드 기반 그룹 매칭 — 공유 키워드 N개 이상이면 같은 사건 그룹으로 판단
TITLE_KEYWORD_MATCH_COUNT = 3

# 사건명에서 자주 등장하는 일반 법률/분류 용어 (유사도 매칭 시 제외)
_CASE_STOPWORDS = {
    "소송", "분쟁", "사건", "피해", "소비자", "유출", "논란", "문제",
    "관련", "사태", "조사", "처리", "대응", "보상", "청구", "재판",
    "판결", "기소", "수사", "검찰", "경찰", "법원", "소송중",
    "민원", "접수", "안내", "경고", "주의", "예방", "위반", "혐의",
    "의혹", "인상", "인하", "확대", "축소", "폭리", "피싱", "스미싱",
    # 기사 제목에서 그룹핑에 의미 없는 추가 단어
    "기자", "뉴스", "보도", "취재", "단독", "속보", "긴급", "확인",
    "발표", "주장", "강조", "밝혀", "지적", "제기", "요구", "촉구",
    "개선", "추진", "계획", "예정", "전망", "분석", "공개", "제도",
}


def parse_damage_amount(text: str) -> int | None:
    """
    피해 규모 텍스트를 원(KRW) 단위 정수로 파싱.
    파싱 불가(미상, 빈값 등)이면 None 반환.

    예시:
      "약 500억원"        → 50_000_000_000
      "1,200만원"         → 12_000_000
      "2조 3천억원"        → 2_300_000_000_000
      "수백억 원대", "미상" → None
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    # 미상 / 불명 / 알 수 없음 등
    if re.search(r"미상|불명|알\s*수\s*없|불확실|확인\s*안\s*됨|확인\s*불가", text):
        return None

    # 숫자가 전혀 없으면 파싱 불가
    if not re.search(r"\d", text):
        return None

    try:
        # 쉼표, 공백 정규화
        t = re.sub(r",", "", text)

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
            unit = 10_000 if "만" in t[m.end() - 1:m.end() + 1] else 1_000
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

    if not re.search(r"\d", text):
        return None

    try:
        t = re.sub(r",", "", text)

        total = 0

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


def call_openai(messages: list[dict]) -> tuple[str, int, int]:
    """OpenAI GPT-4o API 호출 → (응답텍스트, prompt_tokens, completion_tokens)"""
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,  # type: ignore[arg-type]
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    choice = response.choices[0]
    usage = response.usage
    return (
        choice.message.content or "",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )


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
    """활성 사건 그룹 이름 목록 조회 (is_relevant=True 기사가 있는 그룹만)"""
    groups = (
        CaseGroup.objects.annotate(
            relevant_count=Count(
                "analyses", filter=Q(analyses__is_relevant=True)
            )
        )
        .filter(relevant_count__gt=0)
        .values_list("name", flat=True)
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


def find_or_create_case_group(case_name: str, article_title: str = "", article_date=None) -> CaseGroup | None:
    """사건명으로 기존 CaseGroup을 찾거나 유사도 매칭 후 새로 생성.

    매칭 순서:
      1) case_name 정확 일치
      2) case_name 유사도 매칭 (SequenceMatcher + 토큰 보너스)
      3) 기사 제목 키워드 겹침 매칭 (case_name 매칭 실패 시 fallback)
         — 최근 30일 기사 제목과 TITLE_KEYWORD_MATCH_COUNT개 이상 공유 시 같은 그룹
      4) 새 그룹 생성
    """
    if not case_name:
        return None

    # 1) 정확히 일치하는 그룹
    existing = CaseGroup.objects.filter(name=case_name).first()
    if existing:
        return existing

    # 모든 그룹 한 번에 로드 (이후 단계에서 재사용)
    all_groups = list(CaseGroup.objects.all())

    # 2) case_name 유사도 매칭
    best_match = None
    best_ratio = 0.0
    for group in all_groups:
        ratio = _case_similarity(case_name, group.name)
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = group

    if best_match and best_ratio >= CASE_SIMILARITY_THRESHOLD:
        logger.info(
            "사건 그룹 유사도 매칭: '%s' → '%s' (%.2f)",
            case_name,
            best_match.name,
            best_ratio,
        )
        return best_match

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
            from django.db.models import Subquery, OuterRef
            latest_titles = (
                Analysis.objects.filter(
                    case_group=OuterRef("pk"),
                    article__published_at__gte=recent_cutoff,
                )
                .order_by("-article__published_at")
                .values("article__title")[:1]
            )
            groups_with_titles = (
                CaseGroup.objects.filter(id__in=[g.id for g in all_groups])
                .annotate(latest_title=Subquery(latest_titles))
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
                        title_keywords & _extract_title_keywords(best_kw_match["latest_title"])
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

    # Gemini 우선, OpenAI 폴백
    has_gemini = bool(getattr(settings, "GEMINI_API_KEY", ""))
    has_openai = bool(getattr(settings, "OPENAI_API_KEY", ""))

    if has_gemini:
        primary, fallback = call_gemini, (call_openai if has_openai else None)
        primary_name, fallback_name = "Gemini", "OpenAI"
    elif has_openai:
        primary, fallback = call_openai, None
        primary_name, fallback_name = "OpenAI", None
    else:
        logger.error("LLM API 키가 설정되지 않음 (OPENAI_API_KEY 또는 GEMINI_API_KEY)")
        article.status = "failed"
        article.retry_count += 1
        article.save(update_fields=["status", "retry_count"])
        return False

    try:
        raw_response, prompt_tokens, completion_tokens = primary(messages)
    except Exception:
        logger.exception("%s API 호출 실패: article=%d", primary_name, article.pk)
        if fallback:
            try:
                raw_response, prompt_tokens, completion_tokens = fallback(messages)
            except Exception:
                logger.exception("%s API도 실패: article=%d", fallback_name, article.pk)
                article.status = "failed"
                article.retry_count += 1
                article.save(update_fields=["status", "retry_count"])
                return False
        else:
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

    used_model = settings.GEMINI_MODEL if primary == call_gemini else settings.LLM_MODEL

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
            llm_model=used_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )

    article.status = "analyzed"
    article.save(update_fields=["status"])
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_pending_articles(self):
    """분석 대기(pending/analyzing) 상태의 기사를 일괄 분석"""
    pending = Article.objects.filter(status__in=["pending", "analyzing"]).order_by("collected_at")
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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reanalyze_article(self, article_id: int):
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
