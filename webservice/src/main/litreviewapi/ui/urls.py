from django.urls import include, path

from . import views

urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("register", views.register_request, name="register"),
    path("", views.home_no_project, name="ui_home_no_project"),
    path("projects/<int:project_id>", views.home, name="ui_home"),
    path("project", views.CreateProjectView.as_view(), name="ui_create_project"),
    path("projects/<int:project_id>/edit", views.ProjectView.as_view(), name="ui_project"),
    path("projects/<int:project_id>/uploaddocuments", views.upload_documents, name="ui_upload_documents"),
    path("projects/<int:project_id>/exportdocuments", views.export_documents, name="ui_export_documents"),
    path("projects/<int:project_id>/labeldocuments", views.label_documents, name="ui_label_documents"),
    path("projects/<int:project_id>/labeldocument/<int:document_id>", views.label_document, name="ui_label_document"),
]
