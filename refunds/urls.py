from django.urls import path
from . import views

app_name = "refunds"
urlpatterns = [
    path("", views.queue, name="queue"),
    path("cases/new/", views.create_case, name="new"),
    path("cases/<str:reference>/", views.case_detail, name="detail"),
    path("cases/<str:reference>/action/", views.case_action, name="action"),
    path("demo/seed-legacy/", views.seed_legacy, name="seed_legacy"),
    path("telemetry/", views.telemetry, name="telemetry"),
    path("health/", views.health, name="health"),
]
