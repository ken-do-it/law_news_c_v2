"""수집 → 분석 전체 파이프라인 (Celery 없이 동기 실행)"""
import sys, os, time, django

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from articles.tasks import crawl_news  # noqa: E402
from analyses.tasks import analyze_single_article  # noqa: E402
from articles.models import Article  # noqa: E402


def main():
    t0 = time.time()

    # 1) 수집
    print('\n' + '=' * 50)
    print('  STEP 1: 뉴스 수집')
    print('=' * 50 + '\n')
    new_count = crawl_news()
    print(f'  → 새 기사 {new_count}건 수집됨')

    # 2) 분석
    pending = Article.objects.filter(status__in=['pending', 'analyzing']).order_by('collected_at')
    total = pending.count()
    print('\n' + '=' * 50)
    print(f'  STEP 2: AI 분석 (대기 {total}건)')
    print('=' * 50 + '\n')

    if total == 0:
        print('  → 분석할 기사 없음 — 건너뜀')
    else:
        success = 0
        failed = 0
        for i, article in enumerate(pending, 1):
            t1 = time.time()
            try:
                ok = analyze_single_article(article)
            except Exception as e:
                article.status = 'failed'
                article.retry_count += 1
                article.save(update_fields=['status', 'retry_count'])
                ok = False
                print(f'  [{i}/{total}] ✗ {article.title[:50]}  예외 발생: {e}', flush=True)
                continue
            elapsed_item = time.time() - t1
            if ok:
                success += 1
                tag = '✓'
            else:
                failed += 1
                tag = '✗'
            print(f'  [{i}/{total}] {tag} {article.title[:50]}  ({elapsed_item:.1f}s)', flush=True)

        print(f'\n  → 총 {total}건 (성공 {success}, 실패 {failed})')

    elapsed = time.time() - t0
    print('\n' + '=' * 50)
    print(f'  파이프라인 완료 ({elapsed:.1f}초 소요)')
    print('=' * 50 + '\n')


if __name__ == '__main__':
    main()
