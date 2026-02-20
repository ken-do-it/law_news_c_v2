"""뉴스 수집 (Celery 없이 동기 실행)"""
import sys, os, django

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from articles.tasks import crawl_news_sync  # noqa: E402


def main():
    print('\n[START] 뉴스 수집을 시작합니다...\n')
    result = crawl_news_sync()
    print(f'\n[DONE] 수집 완료: 새 기사 {result}건\n')


if __name__ == '__main__':
    main()


