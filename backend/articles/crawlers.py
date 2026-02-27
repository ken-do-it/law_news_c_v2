"""네이버 뉴스 API 기반 크롤링 모듈"""

import logging
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

# 도메인 → 언론사명 매핑 (네이버 API에 source 필드가 없으므로 URL 기반 추출)
DOMAIN_TO_SOURCE = {
    "news.kbs.co.kr": "KBS",
    "news.sbs.co.kr": "SBS",
    "imnews.imbc.com": "MBC",
    "news.jtbc.co.kr": "JTBC",
    "www.ytn.co.kr": "YTN",
    "news.mbn.co.kr": "MBN",
    "news.tvchosun.com": "TV조선",
    "www.ichannela.com": "채널A",
    "www.chosun.com": "조선일보",
    "www.joongang.co.kr": "중앙일보",
    "www.donga.com": "동아일보",
    "www.hani.co.kr": "한겨레",
    "www.khan.co.kr": "경향신문",
    "www.kmib.co.kr": "국민일보",
    "www.munhwa.com": "문화일보",
    "www.seoul.co.kr": "서울신문",
    "www.segye.com": "세계일보",
    "www.hankookilbo.com": "한국일보",
    "www.yonhapnewstv.co.kr": "연합뉴스TV",
    "www.yna.co.kr": "연합뉴스",
    "www.news1.kr": "뉴스1",
    "www.newsis.com": "뉴시스",
    "www.mk.co.kr": "매일경제",
    "news.mt.co.kr": "머니투데이",
    "www.sedaily.com": "서울경제",
    "www.hankyung.com": "한국경제",
    "news.heraldcorp.com": "헤럴드경제",
    "www.fnnews.com": "파이낸셜뉴스",
    "www.asiae.co.kr": "아시아경제",
    "www.edaily.co.kr": "이데일리",
    "biz.chosun.com": "조선비즈",
    "www.bizwatch.co.kr": "비즈워치",
    "www.joseilbo.com": "조세일보",
    "www.nocutnews.co.kr": "노컷뉴스",
    "www.tf.co.kr": "더팩트",
    "www.dailian.co.kr": "데일리안",
    "www.mediatoday.co.kr": "미디어오늘",
    "www.inews24.com": "아이뉴스24",
    "www.ohmynews.com": "오마이뉴스",
    "www.pressian.com": "프레시안",
    "www.ddaily.co.kr": "디지털데일리",
    "www.dt.co.kr": "디지털타임스",
    "www.bloter.net": "블로터",
    "www.etnews.com": "전자신문",
    "zdnet.co.kr": "지디넷코리아",
    "www.kookje.co.kr": "국제신문",
    "www.busan.com": "부산일보",
    "www.daejonilbo.com": "대전일보",
    "www.imaeil.com": "매일신문",
    "www.kwnews.co.kr": "강원일보",
    "www.kyeonggi.com": "경기일보",
    "sbsfune.sbs.co.kr": "SBS Biz",
    "koreajoongangdaily.joins.com": "코리아중앙데일리",
    "www.koreaherald.com": "코리아헤럴드",
    "www.newstapa.org": "뉴스타파",
    "www.heconomy.co.kr": "한경비즈니스",
    "www.sisain.co.kr": "시사IN",
    "www.sisajournal.com": "시사저널",
    "weekly.donga.com": "주간동아",
    "weekly.chosun.com": "주간조선",
    "weekly.khan.co.kr": "주간경향",
    "h21.hani.co.kr": "한겨레21",
    "jmagazine.joins.com": "중앙SUNDAY",
    "shindonga.donga.com": "신동아",
    "economist.co.kr": "이코노미스트",
}


def search_naver_news(keyword: str, display: int = 100, start: int = 1) -> list[dict]:
    """네이버 뉴스 검색 API 호출"""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }
    params = {
        "query": keyword,
        "display": display,
        "start": start,
        "sort": "date",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except requests.RequestException:
        logger.exception("네이버 뉴스 API 호출 실패: keyword=%s", keyword)
        return []


def clean_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거"""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_naver_date(date_str: str) -> datetime:
    """네이버 API 날짜 포맷 파싱 (RFC 822)"""
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime.now(tz=timezone.utc)


def extract_source_from_url(original_link: str) -> str:
    """URL 도메인에서 언론사명 추출"""
    try:
        parsed = urlparse(original_link)
        domain = parsed.netloc.lower()
        # www 제거한 도메인도 시도
        domain_no_www = domain.removeprefix("www.")

        for key, name in DOMAIN_TO_SOURCE.items():
            if key in domain or key.removeprefix("www.") == domain_no_www:
                return name
    except Exception:
        pass
    return ""


def extract_source_from_naver_page(naver_url: str) -> str:
    """네이버 뉴스 페이지에서 언론사명 추출"""
    try:
        resp = requests.get(
            naver_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 네이버 뉴스 페이지의 언론사명
        press = soup.select_one(".media_end_head_top_logo img")
        if press and press.get("alt"):
            return str(press["alt"])

        press = soup.select_one("a.media_end_head_top_logo_img img")
        if press and press.get("title"):
            return str(press["title"])

    except Exception:
        pass
    return ""


def fetch_article_content(url: str) -> str:
    """기사 본문 크롤링 — 네이버 뉴스 URL에서 본문 추출"""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 네이버 뉴스 본문 영역
        content_area = (
            soup.select_one("#dic_area")
            or soup.select_one("#articeBody")
            or soup.select_one(".article_body")
            or soup.select_one("article")
        )

        if content_area:
            return content_area.get_text(separator="\n", strip=True)

        # fallback: meta description
        meta = soup.find("meta", {"property": "og:description"})
        if meta and meta.get("content"):
            return str(meta["content"])

        return ""
    except requests.RequestException:
        logger.exception("기사 본문 크롤링 실패: %s", url)
        return ""
