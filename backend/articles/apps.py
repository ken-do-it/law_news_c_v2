from django.apps import AppConfig


class ArticlesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "articles"

    def ready(self):
        from articles.services.scheduler import start_runserver_scheduler

        start_runserver_scheduler()
