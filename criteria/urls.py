from django.urls import path

from . import views

app_name = "criteria"

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("theory/", views.theory, name="theory"),
    path("test-cases/", views.test_cases, name="test_cases"),
    path("test-cases/run", views.test_cases_run, name="test_cases_run"),
    path("test-cases/normalized.json", views.test_cases_normalized_json, name="test_cases_normalized_json"),
    path("export/pdf", views.export_pdf, name="export_pdf"),
    path("api/score", views.api_score, name="api_score"),
]


