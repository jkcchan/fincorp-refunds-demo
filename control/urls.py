from django.urls import path
from . import views

app_name = "control"
urlpatterns = [
    path("", views.changes, name="list"),
    path("new/", views.new, name="new"),
    path("changes/<int:pk>/", views.detail, name="detail"),
    path("changes/<int:pk>/answer/", views.answer, name="answer"),
    path("changes/<int:pk>/action/", views.action, name="action"),
    path("changes/<int:pk>/events/", views.events, name="events"),
]
