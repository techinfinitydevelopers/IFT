from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant'

    def ready(self):
        from . import signals  # noqa: F401 — registers pre/post_save receivers
