"""뉴스 수집 (Celery 없이 동기 실행)"""
import sys, os, io, django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from articles.tasks import crawl_news_sync  # noqa: E402


def main():
    print('\n🔍 뉴스 수집을 시작합니다...\n')
    result = crawl_news_sync()
    print(f'\n✅ 수집 완료: 새 기사 {result}건\n')


if __name__ == '__main__':
    main()


