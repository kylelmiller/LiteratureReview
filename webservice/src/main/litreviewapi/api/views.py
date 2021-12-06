import json

from django.core.serializers.json import Serializer as DefaultSerializer
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .service import DocumentService, ProjectService


class Serializer(DefaultSerializer):
    def serialize_object(self, obj):
        return self.serialize([obj])[1:-1]

    def get_dump_object(self, obj):
        return {**{"id": obj._get_pk_val()}, **self._current}


class UserProjectsView(View):
    def get(self, request):
        return HttpResponse(
            json.dumps(ProjectService.get_projects(request.user)),
            content_type="application/json",
        )

    def post(self, request):
        return HttpResponse(
            json.dumps(
                {
                    "id": ProjectService.create_project(
                        request.user, name=request.POST["name"], description=request.POST["description"]
                    )
                }
            ),
            content_type="application/json",
        )


class UserProjectView(View):
    def get(self, request, project_id):
        try:
            return HttpResponse(
                Serializer().serialize_object(
                    ProjectService.get_project(pk=project_id, owner=request.user, as_dict=False)
                ),
                content_type="application/json",
            )
        except ObjectDoesNotExist:
            return Http404("No project found.")

    def post(self, request, project_id):
        try:
            ProjectService.update_project(
                project_id,
                request.user,
                **{k: v for k, v in request.POST.items() if k in {"name", "description"}},
            )
            return HttpResponse()
        except ObjectDoesNotExist:
            return Http404("No project found.")


class UserDocumentsView(View):
    @transaction.atomic
    def post(self, request, project_id):
        try:
            DocumentService.add_documents(project_id, request.user, [])
            return HttpResponse()
        except ObjectDoesNotExist:
            return Http404("No project found.")


@csrf_exempt
@require_POST
def label_document(request, project_id, document_id):
    if "label" not in request.POST:
        return HttpResponseBadRequest("label is required.")

    DocumentService.update_document(document_id, project_id, user=request.user, label=request.POST["label"])
    return HttpResponse()


@require_GET
def next_document(request, project_id):
    next_document = ProjectService.get_next_document(project_id, request.user)
    return HttpResponse(
        Serializer().serialize_object(next_document) if next_document else None,
        content_type="application/json",
    )


# INTERNAL
@api_view(["POST"])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAdminUser])
def project(request, project_id):
    if "estimated_positive" not in request.data:
        return HttpResponseBadRequest("estimated_positive is required.")
    ProjectService.update_project(project_id, estimated_positive=request.data["estimated_positive"])
    return HttpResponse()


@api_view(["GET"])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAdminUser])
def documents(request, project_id):
    return HttpResponse(
        Serializer().serialize(
            DocumentService.get_documents(project_id, exclude_unlabeled=request.GET.get("labeled", False)).order_by(
                "labeled_date"
            )
        ),
        content_type="application/json",
    )


@api_view(["POST"])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAdminUser])
@transaction.atomic
def documents_order(request, project_id):
    for document in request.data:
        DocumentService.update_document(document["id"], project_id, order=document["order"])
    return HttpResponse()
