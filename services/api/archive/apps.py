from django.apps import AppConfig


class ArchiveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "archive"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import pre_save

        from .api_tokens import revoke_tokens_on_password_change

        pre_save.connect(revoke_tokens_on_password_change, sender=get_user_model(), dispatch_uid="ripiano-revoke-tokens")

        from django.db.models.signals import post_delete

        from .object_access import KIND_OF, forget

        def remove_grants(sender, instance, **kwargs):
            forget(KIND_OF[sender], instance.pk)

        for model in KIND_OF:
            post_delete.connect(remove_grants, sender=model, dispatch_uid=f"ripiano-object-access-{model.__name__}")
