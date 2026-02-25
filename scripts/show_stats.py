"""시스템 현황 통계 출력"""
import sys, os, io, django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone  # noqa: E402
from articles.models import Article, Keyword, MediaSource  # noqa: E402
from analyses.models import Analysis, CaseGroup  # noqa: E402


def main():
    today = timezone.localdate()
    total_articles = Article.objects.count()
    today_articles = Article.objects.filter(collected_at__date=today).count()
    pending = Article.objects.filter(status='pending').count()
    analyzing = Article.objects.filter(status='analyzing').count()
    analyzed = Article.objects.filter(status='analyzed').count()
    failed = Article.objects.filter(status='failed').count()

    total_analyses = Analysis.objects.count()
    high = Analysis.objects.filter(suitability='High').count()
    medium = Analysis.objects.filter(suitability='Medium').count()
    low = Analysis.objects.filter(suitability='Low').count()
    relevant = Analysis.objects.filter(is_relevant=True).count()

    keywords = Keyword.objects.filter(is_active=True).count()
    sources = MediaSource.objects.filter(is_active=True).count()
    case_groups = CaseGroup.objects.count()

    print(f'''
╔══════════════════════════════════════════════════╗
║          법률 분쟁 사건 자동 발굴 시스템           ║
║                시스템 현황 ({today})             ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  📰 기사                                         ║
║     전체: {total_articles:>6}건    오늘 수집: {today_articles:>5}건     ║
║     대기: {pending:>6}건    분석중:    {analyzing:>5}건     ║
║     완료: {analyzed:>6}건    실패:      {failed:>5}건     ║
║                                                  ║
║  🤖 AI 분석                                      ║
║     전체: {total_analyses:>6}건    관련:      {relevant:>5}건     ║
║     High: {high:>6}건    Medium:    {medium:>5}건     ║
║     Low:  {low:>6}건    사건그룹:  {case_groups:>5}개     ║
║                                                  ║
║  ⚙️  설정                                         ║
║     활성 키워드: {keywords:>4}개    활성 언론사: {sources:>4}개   ║
║                                                  ║
╚══════════════════════════════════════════════════╝
''')


if __name__ == '__main__':
    main()
