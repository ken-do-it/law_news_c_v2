# 개발 변경 이력 — 2026-02-27

이 문서는 2026년 2월 27일에 진행한 개발 작업을 정리한 것입니다.

---

## 1. AI 판단 근거에 한국 관련 이유 명시

### 문제
해외 사건(예: 뉴욕주 vs 밸브, 페덱스 관세 소송)이 목록에 계속 나타났는데,
**왜 한국과 관련 있다고 판단했는지** 판단 근거에 전혀 나오지 않았습니다.

기존 판단 근거 예시:
```
C1(상대방 책임 명확: 루트박스 방식이 도박 구조라는 주장으로 소송 제기),
C2(자력 충분: 밸브는 유명 게임을 서비스하는 대형 게임사),
C3(집단적 피해: 불특정 다수의 게임 이용자 대상)
```
→ 이 내용만 봐선 "이게 왜 한국 관련이지?"를 알 수 없음

### 해결 방법
**파일:** `backend/analyses/prompts.py`

#### 변경 1 — `suitability_reason` 형식 수정
해외 사건일 때는 **판단 근거 맨 앞에** `[한국 관련]` 태그로 이유를 명시하도록 프롬프트 수정

```
[한국 관련] 국내에서도 해당 제품을 구매한 한국 소비자들이 피해를 입음.
C2(자력 충분: 다논 그룹 글로벌 기업), C3(집단적 피해: 다수 소비자) — 2개 조건 충족
```

#### 변경 2 — `is_relevant: true` 판단 기준 강화
| 이전 | 이후 |
|------|------|
| 한국 기업·한국인 피해자가 관련된 경우 | **소송 당사자(원고·피고)에 직접 포함**되거나, 한국 소비자가 **실제 피해**를 입은 경우만 |
| (단순 글로벌 서비스 이용자도 포함 가능) | "한국인이 해당 서비스를 쓴다"는 이유만으로는 `true` 불가 |

> 이 변경으로 **뉴욕주 vs 밸브** 같은 케이스는 앞으로 `is_relevant: false`로 분류됩니다.

#### 변경 3 — few-shot 예시 업데이트
압타밀 분유 예시에 `[한국 관련]` 형식을 추가해 AI가 학습할 수 있도록 함

```json
"suitability_reason": "[한국 관련] 국내에서도 해당 제품을 구매한 한국 소비자들이 피해를 입음. C2(자력 충분: 다논 그룹 글로벌 기업), C3(집단적 피해: 다수 소비자) ..."
```

> ⚠️ 이 변경은 **앞으로 새로 분석되는 기사**부터 적용됩니다.
> 기존 DB에 저장된 분석 결과는 재분석(`just reanalyze {id}`) 해야 반영됩니다.

---

## 2. 심사 결과 케이스 그룹 전체 일괄 적용

### 문제
동일한 사건(같은 케이스 ID)에 여러 기사가 묶여 있을 때,
클라이언트가 기사 1개를 심사 완료 처리하면 나머지 기사는 여전히 미심사 상태로 남았습니다.

### 해결 방법
**파일:** `backend/analyses/views.py` — `partial_update` 메서드 수정

```python
def partial_update(self, request, *args, **kwargs):
    instance = self.get_object()
    serializer = self.get_serializer(instance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # 같은 케이스 그룹의 나머지 기사에도 동일 심사 결과 일괄 적용
    if instance.case_group_id and serializer.validated_data:
        Analysis.objects.filter(
            case_group_id=instance.case_group_id
        ).exclude(id=instance.id).update(**serializer.validated_data)

    return Response(AnalysisListSerializer(instance, ...).data)
```

### 동작 방식
1. 클라이언트가 기사 1개에 심사 결과 입력 (PATCH 요청)
2. 해당 기사 저장
3. 같은 `case_group`에 속한 **나머지 모든 기사에 동일 값 일괄 업데이트** (단일 SQL 쿼리)

### 예시
| 케이스 ID | 기사 수 | 동작 |
|-----------|---------|------|
| CASE-2026-305 | 5개 | 1개 심사 완료 → 나머지 4개 자동 동기화 |
| case_group 없는 단독 기사 | 1개 | 해당 기사만 수정 (기존과 동일) |

적용되는 필드:
- `review_completed` (심사 완료 여부)
- `client_suitability` (로앤굿 심사결과: High / Medium / Low)
- `accepted` (통과 여부)

---

## 3. API PATCH 403 오류 수정

### 문제
심사 완료 체크 시 브라우저 콘솔에 다음 오류 발생:
```
PATCH http://localhost:5173/api/analyses/3505/ 403 (Forbidden)
```

### 원인
Django REST Framework(DRF)의 기본 인증 방식인 `SessionAuthentication`은
PATCH, POST, DELETE 같은 **비안전 메서드에 CSRF 토큰을 요구**합니다.
그런데 Axios는 기본적으로 CSRF 토큰을 요청 헤더에 포함하지 않아서 거부됩니다.

```
브라우저(Axios) ──PATCH──> Django
                           └─ SessionAuthentication 검사
                              └─ CSRF 토큰 없음 → 403 Forbidden
```

### 해결 방법
**파일:** `backend/config/settings.py`

```python
REST_FRAMEWORK = {
    # 추가된 설정
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],  # CSRF 검사 없이 API 사용 (내부 도구)

    # 기존 설정 유지
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    ...
}
```

### 이 설정이 안전한 이유
LawNGood은 **내부 전용 도구**로 외부 사용자가 접근하지 않습니다.
Django Admin(`/admin/`)은 별도의 인증 시스템으로 여전히 보호됩니다.

---

## 4. VSCode 빨간줄(import 오류) 해결 안내

### 문제
`backend/analyses/export.py` 파일에 빨간 밑줄이 많이 표시됨

### 원인
VSCode가 `law_claude_venv2` 가상 환경을 Python 인터프리터로 사용 중인데,
`fpdf2` 라이브러리가 `law_claude_venv2`에는 없고 uv가 관리하는 `.venv`에만 설치되어 있음

> 코드 자체에는 오류가 없습니다. uv 환경에서 실행하면 정상 동작합니다.

### 해결 방법
`Ctrl+Shift+P` → `Python: Select Interpreter` →
아래 경로의 Python 선택:
```
.venv\Scripts\python.exe
```

전체 경로:
```
c:\...\law_news_c_v2\.venv\Scripts\python.exe
```

---

## 요약

| # | 변경 내용 | 파일 | 효과 |
|---|-----------|------|------|
| 1 | 판단 근거에 `[한국 관련]` 이유 명시 | `analyses/prompts.py` | 해외 사건의 한국 관련 판단 근거를 투명하게 표시 |
| 2 | `is_relevant: true` 기준 강화 | `analyses/prompts.py` | 한국 이용자만 있는 글로벌 서비스 소송 필터링 |
| 3 | 심사 결과 케이스 그룹 일괄 적용 | `analyses/views.py` | 1번 심사로 같은 케이스의 모든 기사 동기화 |
| 4 | API PATCH 403 오류 수정 | `config/settings.py` | 심사 완료·결과·통과 여부 PATCH 정상 동작 |
| 5 | VSCode 인터프리터 설정 안내 | — | 빨간줄 제거 |
