"""수집 → 분석 전체 파이프라인 (Celery 없이 동기 실행)"""
import sys, os, io, time, django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from articles.tasks import crawl_news_sync  # noqa: E402
from analyses.tasks import analyze_pending_articles  # noqa: E402
from articles.models import Article  # noqa: E402


def main():
    t0 = time.time()

    # 1) 수집
    print('\n' + '=' * 50)
    print('  STEP 1: 뉴스 수집')
    print('=' * 50 + '\n')
    new_count = crawl_news_sync()
    print(f'  → 새 기사 {new_count}건 수집됨')

    # 2) 분석
    pending = Article.objects.filter(status='pending').count()
    print('\n' + '=' * 50)
    print(f'  STEP 2: AI 분석 (대기 {pending}건)')
    print('=' * 50 + '\n')

    if pending > 0:
        result = analyze_pending_articles()
        print(f'  → 총 {result["total"]}건 '
              f'(성공 {result["success"]}, 실패 {result["failed"]})')
    else:
        print('  → 분석할 기사 없음 — 건너뜀')

    elapsed = time.time() - t0
    print('\n' + '=' * 50)
    print(f'  파이프라인 완료 ({elapsed:.1f}초 소요)')
    print('=' * 50 + '\n')


if __name__ == '__main__':
    main()
