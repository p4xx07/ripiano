from django.apps import AppConfig


class ArchiveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "archive"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import pre_save

        from .api_tokens import revoke_tokens_on_password_change

        pre_save.connect(revoke_tokens_on_password_change, sender=get_user_model(), dispatch_uid="ripiano-revoke-tokens")
