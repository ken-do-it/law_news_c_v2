"""LLM 분석 Celery 태스크 (Celery 제외 및 Gemini 강제 버전)"""

import logging
from difflib import SequenceMatcher

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
    """OpenAI GPT API 호출"""
    # 사용하지 않더라도 혹시 모를 호출에 대비해 남겨둠 (실제 호출되면 안 됨)
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
    """Gemini API 호출 (google.genai SDK, JSON 안정화 재시도 포함)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    model_name = "gemini-2.5-flash"

    base_prompt = "\n\n".join(f"[{m['role']}]: {m['content']}" for m in messages)
    retry_suffix = (
        "\n\nIMPORTANT: Return ONLY a valid JSON object. "
        "Do not include markdown fences, comments, or extra text."
    )

    last_text = ""
    for attempt in range(2):
        prompt = base_prompt if attempt == 0 else base_prompt + retry_suffix

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=settings.LLM_TEMPERATURE,
                response_mime_type="application/json",
                # max_output_tokens 미설정 → 모델 기본값 사용 (Gemini는 충분히 큼)
            ),
        )

        text = (response.text or "").strip()
        last_text = text

        # 1차 필터: JSON object 형태 흔적이 있으면 반환 (정밀 파싱은 validator에서 수행)
        if "{" in text and "}" in text:
            return text, 0, 0

        logger.warning("Gemini JSON 형태 미충족, 재시도 예정: attempt=%d", attempt + 1)

    return last_text, 0, 0


def get_existing_case_names() -> list[str]:
    """활성 사건 그룹 이름 목록 조회 (is_relevant=True 기사가 있는 그룹만)."""
    groups = (
        CaseGroup.objects.annotate(
            relevant_count=Count("analyses", filter=Q(analyses__is_relevant=True))
        )
        .filter(relevant_count__gt=0)
        .values_list("name", flat=True)
    )
    return list(groups)


def _case_similarity(a: str, b: str) -> float:
    """핵심 엔티티 기반 사건명 유사도 (stopword 제외)."""
    seq_ratio = SequenceMatcher(None, a, b).ratio()

    tokens_a = {t for t in a.split() if len(t) >= 2 and t not in _CASE_STOPWORDS}
    tokens_b = {t for t in b.split() if len(t) >= 2 and t not in _CASE_STOPWORDS}

    shared = tokens_a & tokens_b
    if shared:
        bonus = min(len(shared) * 0.25, 0.5)
        return min(seq_ratio + bonus, 1.0)

    for t in tokens_a:
        if len(t) >= 3 and t in b:
            return min(seq_ratio + 0.25, 1.0)
    for t in tokens_b:
        if len(t) >= 3 and t in a:
            return min(seq_ratio + 0.25, 1.0)

    return seq_ratio


def find_or_create_case_group(case_name: str) -> CaseGroup | None:
    """사건명으로 기존 CaseGroup을 찾거나 유사도 매칭 후 새로 생성."""
    if not case_name:
        return None

    existing = CaseGroup.objects.filter(name=case_name).first()
    if existing:
        return existing

    best_match = None
    best_ratio = 0.0
    for group in CaseGroup.objects.all():
        ratio = _case_similarity(case_name, group.name)
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = group

    if best_match and best_ratio >= CASE_SIMILARITY_THRESHOLD:
        logger.info(
            "사건 그룹 유사도 매칭: '%s' -> '%s' (%.2f)",
            case_name,
            best_match.name,
            best_ratio,
        )
        return best_match

    case_id = CaseGroup.generate_next_case_id()
    return CaseGroup.objects.create(case_id=case_id, name=case_name)


def analyze_single_article(article: Article) -> bool:
    """단일 기사 분석 -> 성공 여부 반환."""
    article.status = "analyzing"
    article.save(update_fields=["status"])

    existing_case_names = get_existing_case_names()
    messages = build_messages(article.title, article.content, existing_case_names)

    # Force Gemini usage (ignore OpenAI key check for priority)
    primary = call_gemini
    primary_name = "Gemini"

    if not getattr(settings, "GEMINI_API_KEY", ""):
        logger.error("GEMINI_API_KEY가 설정되지 않았습니다.")
        article.status = "failed"
        article.retry_count += 1
        article.save(update_fields=["status", "retry_count"])
        return False

    try:
        raw_response, prompt_tokens, completion_tokens = primary(messages)
    except Exception:
        logger.exception("%s API 호출 실패: article=%d", primary_name, article.pk)
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


def analyze_pending_articles(self=None):
    """분석 대기(pending) 상태의 기사를 일괄 분석."""
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


def reanalyze_article(article_id: int):
    """특정 기사 재분석."""
    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        logger.error("기사를 찾을 수 없음: %d", article_id)
        return False

    Analysis.objects.filter(article=article).delete()
    article.status = "pending"
    article.save(update_fields=["status"])

    return analyze_single_article(article)
