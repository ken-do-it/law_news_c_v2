from django.core.management.base import BaseCommand

from articles.models import Keyword, MediaSource


class Command(BaseCommand):
    help = "초기 키워드 및 언론사 데이터 입력 (80개 언론사)"

    def handle(self, *args, **options):
        # 수집 키워드 (가이드라인 기준)
        keywords = ["소송", "손해배상", "집단소송", "공동소송", "피해자", "피해보상", "피해구제"]
        for word in keywords:
            obj, created = Keyword.objects.get_or_create(word=word)
            if created:
                self.stdout.write(f"  키워드 추가: {word}")

        # 총 80개 언론사 (클라이언트 요청 84개 중 수집 불가 4개 제외)
        # 제외: 대구MBC, 레이디경향, 머니S, 월간 산
        sources = {
            # 종합 (10개)
            "종합": [
                "경향신문", "국민일보", "동아일보", "문화일보", "서울신문",
                "세계일보", "조선일보", "중앙일보", "한겨레", "한국일보",
            ],
            # 방송/통신 (12개)
            "방송/통신": [
                "뉴스1", "뉴시스", "연합뉴스", "연합뉴스TV", "채널A",
                "한국경제TV", "JTBC", "KBS", "MBC", "MBN", "SBS", "SBS Biz",
                "TV조선", "YTN",
            ],
            # 경제 (11개)
            "경제": [
                "매일경제", "머니투데이", "비즈워치", "서울경제", "아시아경제",
                "이데일리", "조선비즈", "조세일보", "파이낸셜뉴스", "한국경제",
                "헤럴드경제",
            ],
            # 인터넷 (8개)
            "인터넷": [
                "노컷뉴스", "더팩트", "데일리안", "미디어오늘",
                "아이뉴스24", "오마이뉴스", "프레시안",
            ],
            # IT (5개)
            "IT/전문": [
                "디지털데일리", "디지털타임스", "블로터", "전자신문", "지디넷코리아",
            ],
            # 매거진 (11개) — 제외: 레이디경향, 월간 산
            "매거진": [
                "더스쿠프", "매경이코노미", "시사IN", "시사저널",
                "신동아", "이코노미스트", "주간경향", "주간동아",
                "주간조선", "중앙SUNDAY", "한겨레21", "한경비즈니스",
            ],
            # 전문지 (10개)
            "전문지": [
                "기자협회보", "농민신문", "뉴스타파", "동아사이언스",
                "여성신문", "일다", "코리아중앙데일리", "코리아헤럴드",
                "코메디닷컴", "헬스조선",
            ],
            # 지역 (10개) — 제외: 대구MBC
            "지역": [
                "강원도민일보", "강원일보", "경기일보", "국제신문",
                "대전일보", "매일신문", "부산일보", "전주MBC",
                "CJB청주방송", "JIBS", "KBC광주방송",
            ],
        }

        total_added = 0
        for category, names in sources.items():
            for name in names:
                obj, created = MediaSource.objects.get_or_create(name=name)
                if created:
                    total_added += 1
                    self.stdout.write(f"  [{category}] {name}")

        total = MediaSource.objects.count()
        self.stdout.write(f"\n신규 추가: {total_added}개 / 전체 언론사: {total}개")
        self.stdout.write("초기 데이터 입력 완료!")
