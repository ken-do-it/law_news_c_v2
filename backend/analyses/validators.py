"""LLM 응답 검증 모듈"""

import json
import logging
import re

logger = logging.getLogger(__name__)

VALID_SUITABILITY = {"High", "Medium", "Low"}
VALID_STAGES = {"피해 발생", "관련 절차 진행", "소송중", "판결 선고", "종결"}


def _extract_json_object(text: str) -> str:
    """코드블록/부가문구를 제거하고 JSON object 부분만 추출."""
    if not text:
        return text

    s = text.strip()

    # ```json ... ``` 코드블록 제거
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        s = s.strip()

    # 첫 '{' ~ 마지막 '}' 구간만 추출
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]

    return s


def validate_and_parse(raw_response: str) -> dict | None:
    """LLM 응답 JSON을 파싱하고 유효성을 검증."""
    cleaned = _extract_json_object(raw_response)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("JSON 파싱 실패: %s", (cleaned or "")[:200])
        return None

    # 필수 필드 체크
    required = ["suitability", "suitability_reason", "case_category", "summary"]
    for field in required:
        if field not in data or not data[field]:
            logger.error("필수 필드 누락: %s", field)
            return None

    # suitability 검증
    if data["suitability"] not in VALID_SUITABILITY:
        logger.warning("잘못된 suitability 값: %s -> Low로 보정", data["suitability"])
        data["suitability"] = "Low"

    # stage 검증
    stage = data.get("stage", "")
    if stage and stage not in VALID_STAGES:
        logger.warning("잘못된 stage 값: %s -> 빈값으로 보정", stage)
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
    if "is_relevant" in data and not isinstance(data["is_relevant"], bool):
        data["is_relevant"] = True

    # summary 길이 제한
    if len(data.get("summary", "")) > 1000:
        data["summary"] = data["summary"][:1000]

    return data
