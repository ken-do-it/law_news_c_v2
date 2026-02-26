"""LLM 응답 검증 모듈"""

import json
import logging

logger = logging.getLogger(__name__)

VALID_SUITABILITY = {"High", "Medium", "Low"}
VALID_STAGES = {"피해 발생", "관련 절차 진행", "소송중", "판결 선고", "종결"}
NOT_APPLICABLE_STAGES = {"해당 없음", "N/A", "n/a", "NA", "미상", "없음", "해당없음", "-", "null", "None"}


def validate_and_parse(raw_response: str) -> dict | None:
    """LLM 응답 JSON을 파싱하고 유효성 검증."""
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.error("JSON 파싱 실패: %s", raw_response[:200])
        return None

    # Gemini가 가끔 배열([{...}])로 감싸서 반환하는 경우 첫 번째 요소 추출
    if isinstance(data, list):
        if not data:
            logger.error("LLM이 빈 배열 반환")
            return None
        data = data[0]

    if not isinstance(data, dict):
        logger.error("LLM 응답이 dict가 아님: %s", type(data))
        return None

    # is_relevant 먼저 확인 (비관련 기사는 일부 필드 완화)
    is_relevant = data.get("is_relevant", True)
    if not isinstance(is_relevant, bool):
        is_relevant = True

    # 필수 필드 체크
    required = ["suitability", "suitability_reason", "summary"]
    if is_relevant:
        required.append("case_category")
    for field in required:
        if field not in data or not data[field]:
            logger.error("필수 필드 누락: %s", field)
            return None

    # 비관련 기사의 case_category 기본값
    if not is_relevant and not data.get("case_category"):
        data["case_category"] = "해당 없음"

    # suitability 검증
    if data["suitability"] not in VALID_SUITABILITY:
        logger.warning("잘못된 suitability 값: %s → Low로 보정", data["suitability"])
        data["suitability"] = "Low"

    # stage 검증
    stage = data.get("stage", "")
    if stage and stage not in VALID_STAGES:
        if stage in NOT_APPLICABLE_STAGES:
            data["stage"] = ""
        else:
            logger.warning("잘못된 stage 값: %s → 빈값으로 보정", stage)
            data["stage"] = ""

    # 기본값 설정
    defaults = {
        "defendant": "",
        "damage_amount": "미상",
        "victim_count": "미상",
        "stage": "",
        "stage_detail": "",
        "case_name": "",
        "is_relevant": True,
    }
    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default

    # is_relevant 검증 (boolean이 아닌 값은 True로 보정)
    if "is_relevant" in data:
        if not isinstance(data["is_relevant"], bool):
            data["is_relevant"] = True

    # summary 길이 제한
    if len(data.get("summary", "")) > 1000:
        data["summary"] = data["summary"][:1000]

    return data
