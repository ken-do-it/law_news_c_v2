"""분석 결과 엑셀 내보내기"""
import sys, os, io, django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from analyses.models import Analysis  # noqa: E402


def main():
    try:
        import openpyxl
    except ImportError:
        print('\n❌ openpyxl이 설치되어 있지 않습니다.')
        print('   pip install openpyxl\n')
        sys.exit(1)

    analyses = Analysis.objects.select_related(
        'article', 'article__source', 'case_group',
    ).filter(is_relevant=True).order_by('-analyzed_at')

    if not analyses.exists():
        print('\n📭 내보낼 분석 결과가 없습니다.\n')
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '분석결과'

    headers = [
        'ID', '적합도', '기사제목', '사건분야', '상대방',
        '피해규모', '피해자수', '단계', '단계상세',
        '사건ID', '사건명', '출처', '발행일', '분석일', '요약',
    ]
    ws.append(headers)

    for a in analyses:
        ws.append([
            a.id,
            a.suitability,
            a.article.title,
            a.case_category,
            a.defendant or '',
            a.damage_amount or '',
            a.victim_count or '',
            a.stage,
            a.stage_detail or '',
            a.case_group.case_id if a.case_group else '',
            a.case_group.name if a.case_group else '',
            a.article.source.name if a.article.source else '',
            str(a.article.published_at)[:10] if a.article.published_at else '',
            str(a.analyzed_at)[:10] if a.analyzed_at else '',
            a.summary,
        ])

    out_dir = Path(__file__).resolve().parent.parent / 'exports'
    out_dir.mkdir(exist_ok=True)
    filename = f'analyses_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    out_path = out_dir / filename
    wb.save(out_path)

    print(f'\n📥 엑셀 내보내기 완료: {out_path}')
    print(f'   총 {analyses.count()}건\n')


if __name__ == '__main__':
    main()
