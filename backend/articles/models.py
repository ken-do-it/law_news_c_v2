from django.db import models


class MediaSource(models.Model):
    name = models.CharField("언론사명", max_length=100, unique=True)
    url = models.URLField("홈페이지", max_length=500, blank=True, default="")
    is_active = models.BooleanField("활성화", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media_sources"
        ordering = ["name"]
        verbose_name = "언론사"
        verbose_name_plural = "언론사"

    def __str__(self):
        return self.name


class Keyword(models.Model):
    word = models.CharField("키워드", max_length=50, unique=True)
    is_active = models.BooleanField("활성화", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "keywords"
        ordering = ["word"]
        verbose_name = "수집 키워드"
        verbose_name_plural = "수집 키워드"

    def __str__(self):
        return self.word


class Article(models.Model):
    STATUS_CHOICES = [
        ("pending", "분석 대기"),
        ("analyzing", "분석 중"),
        ("analyzed", "분석 완료"),
        ("failed", "분석 실패"),
    ]

    source = models.ForeignKey(
        MediaSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name="언론사",
    )
    title = models.CharField("제목", max_length=500)
    content = models.TextField("본문")
    url = models.URLField("기사 URL", max_length=1000, unique=True)
    author = models.CharField("기자", max_length=100, blank=True, default="")
    published_at = models.DateTimeField("게재일")
    collected_at = models.DateTimeField("수집일", auto_now_add=True)
    status = models.CharField(
        "분석 상태",
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    retry_count = models.IntegerField("재시도 횟수", default=0)
    keywords = models.ManyToManyField(
        Keyword,
        through="ArticleKeyword",
        related_name="articles",
        verbose_name="키워드",
    )

    class Meta:
        db_table = "articles"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "뉴스 기사"
        verbose_name_plural = "뉴스 기사"

    def __str__(self):
        return self.title


class ArticleKeyword(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "article_keywords"
        unique_together = ("article", "keyword")
        verbose_name = "기사-키워드"
        verbose_name_plural = "기사-키워드"

    def __str__(self):
        return f"{self.article.title} - {self.keyword.word}"
