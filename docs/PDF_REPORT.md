# PDF 리포트 기능 문서

이 문서는 LawNGood의 **주간/월간 PDF 리포트 자동 생성 기능**을 설명합니다.

---

## 1. 기능 개요

클라이언트(법무법인)가 버튼 하나로 **기간 내 분석 결과를 PDF로 다운로드**할 수 있습니다.

- **주간 리포트**: 오늘 기준 최근 7일 (오늘 포함)
- **월간 리포트**: 이번 달 1일 ~ 오늘

PDF에는 다음 3개 섹션이 포함됩니다:

| 섹션 | 내용 |
|------|------|
| 1. 전체 분석 결과 | 기간 내 High·Medium 등급 기사 전체 |
| 2. 심사 완료 목록 | 위 기사 중 심사 완료(`review_completed=True`) 항목 |
| 3. 심사 통과 목록 | 위 기사 중 최종 통과(`accepted=True`) 항목 |

---

## 2. 사용 방법

### 프론트엔드 버튼

대시보드 우측 상단의 **리포트 다운로드** 버튼을 클릭합니다.

```
주간 리포트 → report_weekly_20260227.pdf
월간 리포트 → report_202602.pdf
```

### API 직접 호출

```
GET /api/analyses/report/?period=weekly
GET /api/analyses/report/?period=monthly
```

응답: `application/pdf` 파일 스트림

---

## 3. PDF 구조

### 표지 (1페이지)

```
┌─────────────────────────────────┐
│       LawNGood 분석 리포트        │
│   2026.02.21 ~ 02.27 (주간)      │
│       생성일: 2026-02-27          │
│                                 │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
│  │ 850  │ │ 320  │ │ 530  │ │  12  │ │
│  │대상기사│ │High  │ │Medium│ │심사통과│ │
│  └──────┘ └──────┘ └──────┘ └──────┘ │
└─────────────────────────────────┘
```

### 섹션 페이지 (2~4페이지)

각 섹션은 새 페이지에서 시작하며, 다음 구조를 가집니다:

```
1. 전체 분석 결과 (High·Medium)
총 850건

┌──┬──────────┬──────────────┬─────┬──────┬─────┬──────┬──────┬───────────────┐
│No│케이스 ID  │기사 제목      │언론사│게재일 │적합도│사건분야│피해규모│요약           │
├──┼──────────┼──────────────┼─────┼──────┼─────┼──────┼──────┼───────────────┤
│1 │CASE-2026-│피해단체들, 3기│MBC  │26.02.│High │인권   │미상   │3기 진실화해를…│
│  │673       │진화위 출범에…  │     │26    │     │      │      │               │
└──┴──────────┴──────────────┴─────┴──────┴─────┴──────┴──────┴───────────────┘
```

### 열 구성 (가로 A4 기준)

| 열 | 너비 | 설명 |
|----|------|------|
| No | 8mm | 순번 |
| 케이스 ID | 22mm | CASE-2026-XXX |
| 기사 제목 | 68mm | 실측 너비 기준 자동 자르기 |
| 언론사 | 18mm | 최대 8자 |
| 게재일 | 20mm | YY.MM.DD 형식 |
| **적합도** | 16mm | **High(빨강) / Medium(노랑)** 색상 강조 |
| 사건 분야 | 24mm | 개인정보, 제조물책임 등 |
| 피해 규모 | 20mm | 금액 또는 미상 |
| **요약** | **70mm** | **실측 너비 기준 자동 자르기** |

> 전체 합계: 266mm (A4 가로 297mm - 여백 각 10mm = 277mm 내)

---

## 4. 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/analyses/views.py` | `/api/analyses/report/` 엔드포인트 |
| `backend/analyses/export.py` | PDF 생성 로직 전체 |
| `frontend/src/lib/api.ts` | `downloadReport()` 함수 |
| `backend/assets/malgun.ttf` | 맑은고딕 일반체 폰트 |
| `backend/assets/malgunbd.ttf` | 맑은고딕 굵은체 폰트 |

---

## 5. 구현 상세

### 5-1. 날짜 필터링 (`views.py`)

```python
# 주간: 오늘 기준 -6일 ~ 오늘 (7일 범위)
date_from = today - timedelta(days=6)

# 월간: 이번 달 1일 ~ 오늘
date_from = today.replace(day=1)

queryset = Analysis.objects.filter(
    suitability__in=["High", "Medium"],
    article__published_at__date__gte=date_from,  # 날짜 필터 적용
).order_by("-analyzed_at")
```

> ⚠️ **이전 버그**: `date_from`을 계산하고도 `filter()`에 넣지 않아 항상 전체 기간이 조회됐습니다.
> 지금은 날짜 필터가 정상 적용됩니다.

### 5-2. 3개 서브셋 분리 (`export.py`)

```python
analyses = list(queryset)            # 전체 (High·Medium, 기간 내)
reviewed = [a for a in analyses if a.review_completed]   # 심사 완료
accepted = [a for a in analyses if a.accepted]           # 심사 통과
```

각 서브셋은 `_render_section_table()` 함수 한 번 호출로 렌더링됩니다.

### 5-3. 텍스트 오버플로우 해결 — `_fit_text()`

#### 문제

한국어는 영문보다 글자 폭이 2~3배 넓습니다.
고정 글자 수 (예: `[:42]`)로 자르면 한국어 텍스트가 셀 밖으로 넘칩니다.

```
# 기존 (잘못된 방식): 42자로 자르지만 한국어가 넘침
summary[:42] + "…"
```

#### 해결

`fpdf2`의 `get_string_width()`는 **현재 폰트 기준으로 텍스트의 실제 mm 너비**를 계산합니다.
이를 이용해 셀 너비(mm)에 맞게 정확히 자릅니다.

```python
def _fit_text(pdf, text: str, max_width: float) -> str:
    """현재 폰트 기준 실측 너비로 텍스트 자르기"""
    if pdf.get_string_width(text) <= max_width:
        return text                      # 이미 칸에 들어가면 그대로 반환
    suffix = "…"
    while text and pdf.get_string_width(text + suffix) > max_width:
        text = text[:-1]                 # 한 글자씩 뒤에서 제거
    return (text + suffix) if text else suffix
```

#### 적용 위치

```python
row_data = [
    ...
    (_fit_text(pdf, article.title,    _COL_WIDTHS[2] - 2), "L"),  # 기사 제목
    (_fit_text(pdf, analysis.summary, _COL_WIDTHS[8] - 2), "L"),  # 요약
    ...
]
```

> `- 2`는 셀 안쪽 좌우 패딩(각 1mm)입니다.

### 5-4. 한글 폰트 설정

fpdf2는 기본적으로 한글을 지원하지 않습니다.
**맑은고딕** TTF 파일을 직접 등록해서 사용합니다.

```python
# backend/assets/ 폴더에 폰트 파일 있어야 함
self.add_font("Malgun", style="",  fname="backend/assets/malgun.ttf")
self.add_font("Malgun", style="B", fname="backend/assets/malgunbd.ttf")

self.set_font("Malgun", "B", 11)   # 굵게
self.set_font("Malgun", "", 7)     # 일반
```

---

## 6. 버그 수정 이력

### 버그 1 — 리포트가 항상 0건으로 표시 (2026-02-27 수정)

**증상**: PDF 다운로드 시 표지의 모든 통계가 0, 기사 목록도 비어 있음

**원인**:
```python
# 수정 전 — review_completed=True 조건 때문에 심사 안 된 기사는 모두 제외됨
queryset = Analysis.objects.filter(
    suitability__in=["High", "Medium"],
    review_completed=True,   # ← 이 조건이 0건의 원인
)
```

**해결**:
```python
# 수정 후 — 심사 여부 관계없이 기간 내 High·Medium 전체 포함
queryset = Analysis.objects.filter(
    suitability__in=["High", "Medium"],
    article__published_at__date__gte=date_from,  # 날짜 필터로 교체
)
```

---

## 7. 프론트엔드 연동 (`api.ts`)

```typescript
export async function downloadReport(period: 'weekly' | 'monthly'): Promise<void> {
  const { data } = await api.get('/analyses/report/', {
    params: { period },
    responseType: 'blob',   // PDF 바이너리 수신
  });

  // 파일명 자동 생성
  const filename = period === 'monthly'
    ? `report_${today.getFullYear()}${month}.pdf`
    : `report_weekly_${dateStr}.pdf`;

  // 브라우저 다운로드 트리거
  const url = window.URL.createObjectURL(data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}
```
