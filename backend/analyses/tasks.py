"""LLM 분석 Celery 태스크"""

import logging
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

# 사건명에서 자주 등장하는 일반 법률/분류 용어 (유사도 매칭 시 제외)
_CASE_STOPWORDS = {
    "소송", "분쟁", "사건", "피해", "소비자", "유출", "논란", "문제",
    "관련", "사태", "조사", "처리", "대응", "보상", "청구", "재판",
    "판결", "기소", "수사", "검찰", "경찰", "법원", "소송중",
    "민원", "접수", "안내", "경고", "주의", "예방", "위반", "혐의",
    "의혹", "인상", "인하", "확대", "축소", "폭리", "피싱", "스미싱",
}


def call_openai(messages: list[dict]) -> tuple[str, int, int]:
    """OpenAI GPT-4o API 호출 → (응답텍스트, prompt_tokens, completion_tokens)"""
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    choice = response.choices[0]
    usage = response.usage
    return (
        choice.message.content,
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )


def call_gemini(messages: list[dict]) -> tuple[str, int, int]:
    """Gemini API 호출 (대체 LLM)"""
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # 메시지를 Gemini 형식으로 변환
    prompt_parts = []
    for msg in messages:
        prompt_parts.append(f"[{msg['role']}]: {msg['content']}")

    response = model.generate_content(
        "\n\n".join(prompt_parts),
        generation_config=genai.types.GenerationConfig(
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_TOKENS,
            response_mime_type="application/json",
        ),
    )
    return response.text, 0, 0


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


def find_or_create_case_group(case_name: str) -> CaseGroup | None:
    """사건명으로 기존 CaseGroup을 찾거나 유사도 매칭 후 새로 생성"""
    if not case_name:
        return None

    # 1) 정확히 일치하는 그룹
    existing = CaseGroup.objects.filter(name=case_name).first()
    if existing:
        return existing

    # 2) 유사도 매칭 — 기존 그룹명과 비교
    best_match = None
    best_ratio = 0.0
    for group in CaseGroup.objects.all():
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

    # 3) 새 그룹 생성
    case_id = CaseGroup.generate_next_case_id()
    return CaseGroup.objects.create(case_id=case_id, name=case_name)


def analyze_single_article(article: Article) -> bool:
    """단일 기사 분석 → 성공 여부 반환"""
    article.status = "analyzing"
    article.save(update_fields=["status"])

    # 기존 사건 그룹 목록을 프롬프트에 주입
    existing_case_names = get_existing_case_names()
    messages = build_messages(article.title, article.content, existing_case_names)

    # .env에 설정된 API 키에 따라 주(primary)/부(fallback) LLM 자동 결정
    has_openai = bool(getattr(settings, "OPENAI_API_KEY", ""))
    has_gemini = bool(getattr(settings, "GEMINI_API_KEY", ""))

    if has_openai:
        primary, fallback = call_openai, (call_gemini if has_gemini else None)
        primary_name, fallback_name = "OpenAI", "Gemini"
    elif has_gemini:
        primary, fallback = call_gemini, None
        primary_name, fallback_name = "Gemini", None
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
    case_group = find_or_create_case_group(parsed.get("case_name", ""))

    Analysis.objects.create(
        article=article,
        case_group=case_group,
        suitability=parsed["suitability"],
        suitability_reason=parsed["suitability_reason"],
        case_category=parsed["case_category"],
        defendant=parsed.get("defendant", ""),
        damage_amount=parsed.get("damage_amount", "미상"),
        victim_count=parsed.get("victim_count", "미상"),
        stage=parsed.get("stage", ""),
        stage_detail=parsed.get("stage_detail", ""),
        summary=parsed["summary"],
        is_relevant=parsed.get("is_relevant", True),
        llm_model=settings.LLM_MODEL,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    article.status = "analyzed"
    article.save(update_fields=["status"])
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_pending_articles(self):
    """분석 대기(pending) 상태의 기사를 일괄 분석"""
    pending = Article.objects.filter(status="pending").order_by("collected_at")
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
