"""대기 중인 기사 AI 분석 (Celery 없이 동기 실행)"""
import sys, os, django

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from analyses.tasks import analyze_pending_articles  # noqa: E402
from articles.models import Article  # noqa: E402


def main():
    pending = Article.objects.filter(status='pending').count()
    if pending == 0:
        print('\n[INFO] 분석 대기 중인 기사가 없습니다.\n')
        return

    print(f'\n[START] AI 분석을 시작합니다 (대기 {pending}건)...\n')
    result = analyze_pending_articles()
    print(f'\n[DONE] 분석 완료: 총 {result["total"]}건 '
          f'(성공 {result["success"]}, 실패 {result["failed"]})\n')


if __name__ == '__main__':
    main()
