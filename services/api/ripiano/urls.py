from django.contrib import admin
from django.urls import path

from archive import metadata_views, views

urlpatterns = [
    path("healthz", views.health),
    path("api/setup", views.setup_owner),
    path("api/session", views.session),
    path("api/documents", views.documents),
    path("api/documents/<uuid:document_id>", views.document_detail),
    path("api/documents/<uuid:document_id>/original", views.download_original),
    path("api/documents/<uuid:document_id>/archive", views.download_archive),
    path("api/documents/<uuid:document_id>/retry", views.retry_document),
    path("api/backups", views.backups),
    path("api/tags", metadata_views.tags),
    path("api/tags/<uuid:tag_id>", metadata_views.tag_detail),
    path("api/rules", metadata_views.rules),
    path("api/rules/<uuid:rule_id>", metadata_views.rule_detail),
    path("admin/", admin.site.urls),
]
