import csv
import io
from typing import List, Dict

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View

from api.service import DocumentService, ProjectService
from .forms import NewUserForm


def register_request(request):
    if request.method == "POST":
        form = NewUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("ui_home_no_project")
        messages.error(request, "Unsuccessful registration. Invalid information.")
    form = NewUserForm()
    return render(request=request, template_name="registration/register.html", context={"register_form": form})


@require_GET
@login_required
def home(request, project_id):
    return render(
        request,
        "ui/home.html",
        {
            "projects": ProjectService.get_projects(request.user),
            "project": ProjectService.get_project(id=project_id, owner=request.user),
        },
    )


@require_GET
@login_required
def home_no_project(request):
    projects = ProjectService.get_projects(request.user, no_cache=True)
    if projects:
        payload = {
            "projects": projects,
            "project": ProjectService.get_project(id=projects[-1]["id"], owner=request.user),
        }
    else:
        payload = None
    return render(request, "ui/home.html", payload)


class CreateProjectView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "ui/createproject.html")

    def post(self, request):
        return HttpResponseRedirect(
            reverse(
                "ui_project",
                args=(
                    ProjectService.create_project(
                        request.user, name=request.POST["name"], description=request.POST["description"]
                    ),
                ),
            )
        )


class ProjectView(LoginRequiredMixin, View):
    def get(self, request, project_id):
        return render(
            request,
            "ui/project.html",
            {
                "project": ProjectService.get_project(pk=project_id, owner=request.user),
                "projects": ProjectService.get_projects(request.user),
            },
        )

    def post(self, request, project_id):
        ProjectService.update_project(
            project_id, user=request.user, name=request.POST["name"], description=request.POST["description"]
        )
        return HttpResponseRedirect(reverse("ui_project", args=(project_id,)))


@require_GET
@login_required
def export_documents(request, project_id):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
    )

    writer = csv.writer(response)
    documents = DocumentService.get_documents(project_id, user=request.user)
    writer.writerow(["Source Id", "Title", "Journal", "Publication Year", "Authors", "Description", "Label"])
    for document in documents:
        writer.writerow(
            [
                document.source_id,
                document.title,
                document.journal if document.journal is not None else "",
                document.publication_date if document.publication_date is not None else "",
                document.authors if document.authors is not None else "",
                document.description if document.description is not None else "",
                document.label if document.label is not None else "",
            ]
        )

    return response


def parse_pubmed_document(io_string: io.StringIO) -> List[Dict[str, str]]:
    """

    :param io_string:
    :return:
    """

    documents_dictionaries = []
    previous_key = None
    for line in io_string.readlines():
        if line == "":
            continue
        if line[:2].strip():
            key, value = line.split("-", 1)
            key = key.strip()
            value = value.strip()
        else:
            key = previous_key
            value = line.strip()
        if key == "PMID":
            documents_dictionaries.append({"source_id": value})
        elif key == "TI":
            if "title" in documents_dictionaries[-1]:
                documents_dictionaries[-1]["title"] += f" {value}"
            else:
                documents_dictionaries[-1]["title"] = value
        elif key == "AB":
            if "description" in documents_dictionaries[-1]:
                documents_dictionaries[-1]["description"] += f" {value}"
            else:
                documents_dictionaries[-1]["description"] = value
        elif key == "FAU":
            if "authors" not in documents_dictionaries[-1]:
                documents_dictionaries[-1]["authors"] = value
            else:
                documents_dictionaries[-1]["authors"] += f"; {value}"
        elif key == "DP":
            documents_dictionaries[-1]["publication_date"] = value
        elif key == "JT":
            documents_dictionaries[-1]["journal"] = value
        previous_key = key
    return documents_dictionaries


@require_POST
@login_required
def upload_documents(request, project_id):
    # Add documents if a pudmed file was attached
    file = request.FILES.get("documents_file")
    if file:
        if not file.name.endswith(".txt"):
            return render(
                request,
                "ui/project.html",
                {
                    "project": ProjectService.get_project(pk=project_id, owner=request.user),
                    "error_message": "File attached is not in PubMed format.",
                },
            )
        DocumentService.add_documents(
            project_id, request.user, parse_pubmed_document(io.StringIO(file.read().decode("UTF-8-sig")))
        )
    return HttpResponseRedirect(reverse("ui_project", args=(project_id,)))


@require_GET
@login_required
def label_documents(request, project_id):
    return render(
        request,
        "ui/labeldocuments.html",
        {
            "document": ProjectService.get_next_document(project_id, request.user),
            "project": ProjectService.get_project(id=project_id, owner=request.user),
            "projects": ProjectService.get_projects(request.user),
        },
    )


@require_POST
@login_required
def label_document(request, project_id, document_id):
    try:
        label = request.POST["label"] == "Include"
    except KeyError:
        # Redisplay the question voting form.
        return render(
            request,
            "ui/labeldocuments.html",
            {
                "project": ProjectService.get_project(pk=project_id, owner=request.user),
                "error_message": "You didn't select a label.",
            },
        )

    DocumentService.update_document(document_id, project_id, request.user, label=label)
    return HttpResponseRedirect(reverse("ui_label_documents", args=(project_id,)))
