"""LLM 응답 검증 모듈"""

import json
import logging

logger = logging.getLogger(__name__)

VALID_SUITABILITY = {"High", "Medium", "Low"}
VALID_STAGES = {"피해 발생", "관련 절차 진행", "소송중", "판결 선고", "종결"}


def validate_and_parse(raw_response: str) -> dict | None:
    """LLM 응답 JSON을 파싱하고 유효성 검증."""
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.error("JSON 파싱 실패: %s", raw_response[:200])
        return None

    # 필수 필드 체크
    required = ["suitability", "suitability_reason", "case_category", "summary"]
    for field in required:
        if field not in data or not data[field]:
            logger.error("필수 필드 누락: %s", field)
            return None

    # suitability 검증
    if data["suitability"] not in VALID_SUITABILITY:
        logger.warning("잘못된 suitability 값: %s → Low로 보정", data["suitability"])
        data["suitability"] = "Low"

    # stage 검증
    stage = data.get("stage", "")
    if stage and stage not in VALID_STAGES:
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
    }
    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default

    # summary 길이 제한
    if len(data.get("summary", "")) > 1000:
        data["summary"] = data["summary"][:1000]

    return data
