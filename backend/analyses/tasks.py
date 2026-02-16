"""LLM 분석 Celery 태스크"""

import logging

from celery import shared_task
from django.conf import settings

from analyses.models import Analysis, CaseGroup
from analyses.prompts import build_messages
from analyses.validators import validate_and_parse
from articles.models import Article

logger = logging.getLogger(__name__)


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


def find_or_create_case_group(case_name: str) -> CaseGroup | None:
    """사건명으로 기존 CaseGroup을 찾거나 새로 생성"""
    if not case_name:
        return None

    # 기존 그룹에서 유사한 이름 검색
    existing = CaseGroup.objects.filter(name=case_name).first()
    if existing:
        return existing

    # 새 그룹 생성
    case_id = CaseGroup.generate_next_case_id()
    return CaseGroup.objects.create(case_id=case_id, name=case_name)


def analyze_single_article(article: Article) -> bool:
    """단일 기사 분석 → 성공 여부 반환"""
    article.status = "analyzing"
    article.save(update_fields=["status"])

    messages = build_messages(article.title, article.content)

    try:
        raw_response, prompt_tokens, completion_tokens = call_openai(messages)
    except Exception:
        logger.exception("OpenAI API 호출 실패, Gemini로 재시도: article=%d", article.pk)
        try:
            raw_response, prompt_tokens, completion_tokens = call_gemini(messages)
        except Exception:
            logger.exception("Gemini API도 실패: article=%d", article.pk)
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
