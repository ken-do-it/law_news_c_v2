"""크롤링 Celery 태스크"""

import logging

from celery import shared_task
from django.db import IntegrityError

from articles.crawlers import (
    clean_html,
    extract_source_from_naver_page,
    extract_source_from_url,
    fetch_article_content,
    parse_naver_date,
    search_naver_news,
)
from articles.models import Article, ArticleKeyword, Keyword, MediaSource

logger = logging.getLogger(__name__)


def _resolve_source(original_link: str, naver_link: str) -> MediaSource | None:
    """originallink 도메인 → 네이버 뉴스 페이지 순으로 언론사를 매칭"""
    # 1) URL 도메인 매핑
    name = extract_source_from_url(original_link)
    if name:
        obj, _ = MediaSource.objects.get_or_create(name=name)
        return obj

    # 2) 네이버 뉴스 페이지에서 언론사 로고 alt 추출
    if "news.naver.com" in naver_link:
        name = extract_source_from_naver_page(naver_link)
        if name:
            obj, _ = MediaSource.objects.get_or_create(name=name)
            return obj

    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_news(self):
    """활성화된 키워드로 네이버 뉴스를 검색하고 DB에 저장"""
    keywords = Keyword.objects.filter(is_active=True)
    total_new = 0

    for keyword in keywords:
        items = search_naver_news(keyword.word)
        logger.info("키워드 '%s': %d건 검색됨", keyword.word, len(items))

        for item in items:
            naver_link = item.get("link", "")
            original_link = item.get("originallink", "")

            # 네이버 뉴스 링크를 기사 URL로 사용 (중복 방지 키)
            article_url = naver_link if "news.naver.com" in naver_link else original_link
            if not article_url:
                continue

            # 중복 체크
            if Article.objects.filter(url=article_url).exists():
                continue

            # 제목 정리
            title = clean_html(item.get("title", ""))
            description = clean_html(item.get("description", ""))
            pub_date = parse_naver_date(item.get("pubDate", ""))

            # 본문 크롤링 (네이버 뉴스 URL인 경우)
            content = ""
            if "news.naver.com" in naver_link:
                content = fetch_article_content(naver_link)
            if not content:
                content = description

            # 언론사 매칭: originallink 도메인 → 네이버 페이지 순
            source = _resolve_source(original_link, naver_link)

            try:
                article = Article.objects.create(
                    title=title,
                    content=content,
                    url=article_url,
                    source=source,
                    published_at=pub_date,
                    status="pending",
                )
                ArticleKeyword.objects.create(article=article, keyword=keyword)
                total_new += 1
            except IntegrityError:
                continue

    logger.info("크롤링 완료: 총 %d건 신규 수집", total_new)

    # 분석 태스크 자동 트리거
    if total_new > 0:
        try:
            from analyses.tasks import analyze_pending_articles

            analyze_pending_articles.delay()
        except Exception:
            logger.exception("분석 태스크 트리거 실패")

    return total_new


@shared_task
def crawl_news_sync():
    """동기식 크롤링 (테스트/수동 실행용) — Celery 없이 직접 호출"""
    return crawl_news()
