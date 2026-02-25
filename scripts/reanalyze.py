"""특정 기사 재분석"""
import sys, os, io, django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from analyses.tasks import reanalyze_article  # noqa: E402
from articles.models import Article  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print('사용법: python scripts/reanalyze.py <article_id>')
        sys.exit(1)

    article_id = int(sys.argv[1])

    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        print(f'\n❌ 기사 ID {article_id}를 찾을 수 없습니다.\n')
        sys.exit(1)

    print(f'\n🔄 재분석 시작: [{article_id}] {article.title[:60]}...\n')
    success = reanalyze_article(article_id=article_id)

    if success:
        print('\n✅ 재분석 완료\n')
    else:
        print('\n❌ 재분석 실패\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
