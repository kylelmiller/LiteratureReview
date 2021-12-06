from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views

urlpatterns = [
    # external
    # path("projects", csrf_exempt(views.UserProjectsView.as_view()), name="user_projects"),
    # path(
    #     "projects/<int:project_id>",
    #     csrf_exempt(views.UserProjectView.as_view()),
    #     name="user_project",
    # ),
    # path(
    #     "projects/<int:project_id>/documents",
    #     csrf_exempt(views.UserDocumentsView.as_view()),
    #     name="user_documents",
    # ),
    # path(
    #     "projects/<int:project_id>/documents/<int:document_id>",
    #     views.label_document,
    #     name="user_document",
    # ),
    # path("projects/<int:project_id>/nextdocument", views.next_document, name="next_document"),
    # internal
    path("projects/<int:project_id>", views.project, name="internal_project"),
    path("projects/<int:project_id>/documents", views.documents, name="internal_documents"),
    path("projects/<int:project_id>/documentsorder", views.documents_order, name="internal_documents_order"),
]
