"""엑셀 내보내기 모듈"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_analyses_to_excel(queryset) -> io.BytesIO:
    """분석 결과를 .xlsx 파일로 내보내기"""
    wb = Workbook()
    ws = wb.active
    ws.title = "분석 결과"

    # 헤더 스타일
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = [
        "No",
        "케이스 ID",
        "기사 제목",
        "언론사",
        "게재일",
        "적합도",
        "판단 근거",
        "사건 분야",
        "상대방",
        "피해 규모",
        "피해자 수",
        "진행 단계",
        "진행 상세",
        "요약",
        "원문 링크",
    ]

    # 헤더 작성
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # 적합도 배경색
    suit_fills = {
        "High": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
        "Medium": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
        "Low": PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid"),
    }

    # 데이터 작성
    for idx, analysis in enumerate(queryset, 1):
        article = analysis.article
        case_id = analysis.case_group.case_id if analysis.case_group else ""
        row = idx + 1

        values = [
            idx,
            case_id,
            article.title,
            article.source.name if article.source else "",
            article.published_at.strftime("%Y-%m-%d") if article.published_at else "",
            analysis.suitability,
            analysis.suitability_reason,
            analysis.case_category,
            analysis.defendant,
            analysis.damage_amount,
            analysis.victim_count,
            analysis.stage,
            analysis.stage_detail,
            analysis.summary,
            article.url,
        ]

        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)

        # 적합도 셀 색상
        suit_cell = ws.cell(row=row, column=6)
        fill = suit_fills.get(analysis.suitability)
        if fill:
            suit_cell.fill = fill

    # 열 너비 조정
    col_widths = [5, 16, 40, 12, 12, 8, 50, 15, 15, 15, 12, 12, 20, 60, 40]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # 첫 행 고정
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
