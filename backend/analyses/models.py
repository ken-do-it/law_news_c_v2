import datetime

from django.db import models


class CaseGroup(models.Model):
    """유사 사건 자동 그룹핑 — LLM이 분석 시 사건명을 기준으로 자동 배정"""

    case_id = models.CharField(
        "케이스 ID",
        max_length=30,
        unique=True,
        help_text="예: CASE-2026-001",
    )
    name = models.CharField("사건명", max_length=200, help_text="예: 쿠팡 개인정보 유출")
    description = models.TextField("사건 설명", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "case_groups"
        ordering = ["-created_at"]
        verbose_name = "사건 그룹"
        verbose_name_plural = "사건 그룹"

    def __str__(self):
        return f"[{self.case_id}] {self.name}"

    @classmethod
    def generate_next_case_id(cls):
        year = datetime.date.today().year
        prefix = f"CASE-{year}-"
        last = (
            cls.objects.filter(case_id__startswith=prefix)
            .order_by("-case_id")
            .first()
        )
        if last:
            seq = int(last.case_id.split("-")[-1]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:03d}"


class Analysis(models.Model):
    SUITABILITY_CHOICES = [
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]
    STAGE_CHOICES = [
        ("피해 발생", "피해 발생"),
        ("관련 절차 진행", "관련 절차 진행"),
        ("소송중", "소송중"),
        ("판결 선고", "판결 선고"),
        ("종결", "종결"),
    ]

    article = models.OneToOneField(
        "articles.Article",
        on_delete=models.CASCADE,
        related_name="analysis",
        verbose_name="기사",
    )
    case_group = models.ForeignKey(
        CaseGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analyses",
        verbose_name="사건 그룹",
    )

    # 가이드라인 6개 분석 항목
    suitability = models.CharField(
        "소송금융 적합도",
        max_length=10,
        choices=SUITABILITY_CHOICES,
        db_index=True,
    )
    suitability_reason = models.TextField("판단 근거")
    case_category = models.CharField("사건 분야", max_length=100, db_index=True)
    defendant = models.CharField("상대방", max_length=200, blank=True, default="")
    damage_amount = models.CharField("피해 규모(금액)", max_length=200, blank=True, default="")
    damage_amount_num = models.BigIntegerField(
        "피해 규모(원)",
        null=True,
        blank=True,
        db_index=True,
        help_text="파싱된 숫자 (원 단위). 미상이면 null.",
    )
    victim_count = models.CharField("피해자 수", max_length=200, blank=True, default="")
    victim_count_num = models.IntegerField(
        "피해자 수(숫자)",
        null=True,
        blank=True,
        db_index=True,
        help_text="파싱된 숫자. 미상이면 null.",
    )
    stage = models.CharField(
        "진행 단계",
        max_length=50,
        choices=STAGE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    stage_detail = models.CharField("진행 단계 상세", max_length=200, blank=True, default="")
    summary = models.TextField("요약")

    # 법적 분쟁 관련 여부 (LLM이 판단)
    is_relevant = models.BooleanField(
        "법적 분쟁 관련",
        default=True,
        db_index=True,
        help_text="법적 분쟁/소송과 관련 없는 기사는 False",
    )

    # 로앤굿 심사 필드 (클라이언트 입력)
    review_completed = models.BooleanField(
        "심사 완료",
        default=False,
        db_index=True,
        help_text="로앤굿이 해당 사건을 검토 완료한 경우 True",
    )
    client_suitability = models.CharField(
        "로앤굿 심사 결과",
        max_length=10,
        choices=SUITABILITY_CHOICES,
        null=True,
        blank=True,
        help_text="로앤굿이 직접 판단한 소송 적합도 (AI 결과와 다를 수 있음)",
    )
    accepted = models.BooleanField(
        "통과 여부",
        default=False,
        db_index=True,
        help_text="수임 대상으로 채택 여부 — 심사 완료 이후에만 True 가능",
    )

    # LLM 메타 정보
    llm_model = models.CharField("사용 모델", max_length=50, default="gpt-4o")
    prompt_tokens = models.IntegerField("프롬프트 토큰", default=0)
    completion_tokens = models.IntegerField("응답 토큰", default=0)
    analyzed_at = models.DateTimeField("분석 시각", auto_now_add=True)

    class Meta:
        db_table = "analyses"
        ordering = ["-analyzed_at"]
        indexes = [
            models.Index(fields=["-analyzed_at"]),
            models.Index(fields=["suitability"]),
            models.Index(fields=["case_category"]),
        ]
        verbose_name = "AI 분석 결과"
        verbose_name_plural = "AI 분석 결과"

    def __str__(self):
        return f"[{self.suitability}] {self.article.title}"
