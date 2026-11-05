from django.contrib import admin
from django.urls import path

from archive import agent_views, metadata_views, physical_views, views

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
    path("api/correspondents", metadata_views.correspondents),
    path("api/correspondents/<uuid:correspondent_id>", metadata_views.correspondent_detail),
    path("api/document-types", metadata_views.document_types),
    path("api/document-types/<uuid:type_id>", metadata_views.document_type_detail),
    path("api/filing-rules", metadata_views.filing_rules),
    path("api/filing-rules/<uuid:rule_id>", metadata_views.filing_rule_detail),
    path("api/rules", metadata_views.rules),
    path("api/rules/<uuid:rule_id>", metadata_views.rule_detail),
    path("api/locations", physical_views.locations),
    path("api/locations/<uuid:location_id>", physical_views.location_detail),
    path("api/documents/<uuid:document_id>/copies", physical_views.document_copies),
    path("api/copies/<uuid:copy_id>", physical_views.copy_detail),
    path("api/copies/<uuid:copy_id>/history", physical_views.copy_history),
    path("api/copies/<uuid:copy_id>/label", physical_views.printable_label),
    path("api/stickers/<str:sticker_code>", physical_views.sticker_lookup),
    path("api/agents", agent_views.grants),
    path("api/agents/<uuid:grant_id>", agent_views.grant_detail),
    path("api/agents/events", agent_views.events),
    path("admin/", admin.site.urls),
]
