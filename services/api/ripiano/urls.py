from django.contrib import admin
from django.urls import path

from archive import views

urlpatterns = [
    path("healthz", views.health),
    path("api/setup", views.setup_owner),
    path("api/session", views.session),
    path("api/documents", views.documents),
    path("api/documents/<uuid:document_id>", views.document_detail),
    path("api/documents/<uuid:document_id>/original", views.download_original),
    path("api/backups", views.backups),
    path("admin/", admin.site.urls),
]
