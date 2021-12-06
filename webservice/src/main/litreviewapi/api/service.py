from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import json
import redis
from confluent_kafka import SerializingProducer
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist

from .models import Project, Document


# This is wrong and should be moved to a setting file
import os

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
kafka_producer = SerializingProducer(
    {
        "bootstrap.servers": os.environ.get("KAFKA_BROKERS"),
        "key.serializer": lambda key, ctx: str(key).encode("utf-8"),
        "value.serializer": lambda value, ctx: json.dumps({k: int(v) for k, v in value.items()}).encode("utf-8"),
    }
)


class ProjectService:
    @staticmethod
    def __set_redis_projects_cache(user: User, projects: List[Dict[str, Union[int, str]]]) -> None:
        name = f"projects:{user.pk}"
        redis_client.delete(name)
        for project in projects:
            redis_client.rpush(name, json.dumps(project))

    @staticmethod
    def get_project(as_dict=True, **kwargs) -> Union[Dict[str, Any], Project, None]:
        project = Project.objects.get(**kwargs)
        if as_dict:
            return {
                "id": project.pk,
                "owner": project.owner.pk,
                "name": project.name,
                "description": project.description,
                "created_date": project.created_date.strftime("%Y-%m-%d %H:%M"),
                "estimated_positive": project.estimated_positive,
                "positive_labels": project.document_set.filter(label=1).count(),
                "negative_labels": project.document_set.filter(label=0).count(),
                "total_documents": project.document_set.count(),
            }
        return project

    @staticmethod
    def get_projects(user: User, no_cache=False) -> List[Dict[str, Any]]:
        key_name = f"projects:{user.pk}"
        if no_cache or not redis_client.exists(key_name):
            projects = Project.objects.filter(owner=user)
            ProjectService.__set_redis_projects_cache(
                user, [{"id": project.pk, "name": project.name} for project in projects]
            )

        return [json.loads(redis_client.lindex(key_name, i)) for i in range(0, redis_client.llen(key_name))]

    @staticmethod
    def create_project(user: User, **kwargs) -> int:
        projects = ProjectService.get_projects(user)
        if len(projects) >= 3:
            raise PermissionDenied("You are only allowed to have three active projects.")

        project = Project(**{**{"owner": user}, **{k: v for k, v in kwargs.items() if k in {"name", "description"}}})
        project.save()

        projects.append({"id": project.pk, "name": project.name})
        ProjectService.__set_redis_projects_cache(user, projects)

        return project.id

    @staticmethod
    def update_project(
        project_id: int, user: Optional[User] = None, name=None, description=None, estimated_positive=None
    ) -> None:
        project = (
            ProjectService.get_project(pk=project_id, owner=user, as_dict=False)
            if user
            else ProjectService.get_project(pk=project_id, as_dict=False)
        )
        if not project or (user and project.owner != user):
            raise ObjectDoesNotExist()
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if estimated_positive is not None:
            project.estimated_positive = estimated_positive
        project.save()

        if name is not None:
            cached_projects = ProjectService.get_projects(project.owner)
            for cached_project in cached_projects:
                if cached_project["id"] == project.pk:
                    cached_project["name"] = name
                    break
            ProjectService.__set_redis_projects_cache(user, cached_projects)

    @staticmethod
    def get_next_document(project_id: int, user: User) -> Optional[Document]:
        remaining_documents = (
            Project.objects.get(pk=project_id, owner=user).document_set.filter(label=None).order_by("order")
        )
        return remaining_documents[0] if len(remaining_documents) > 0 else None


class DocumentService:
    @staticmethod
    def __set_redis_project_cache(project: Project) -> None:
        name = f"project:{project['id']}"
        redis_client.hset(name, "positive_labels", project["positive_labels"])
        redis_client.hset(name, "negative_labels", project["negative_labels"])
        redis_client.hset(name, "total_documents", project["total_documents"])

    @staticmethod
    def get_documents(project_id: int, user: User = None, exclude_unlabeled: bool = True) -> List[Document]:
        if user:
            return (
                Document.objects.filter(project__pk=project_id, project__owner=user, label__isnull=False)
                if exclude_unlabeled
                else Document.objects.filter(project__pk=project_id, project__owner=user)
            )
        else:
            return (
                Document.objects.filter(project__pk=project_id, label__isnull=False)
                if exclude_unlabeled
                else Document.objects.filter(project__pk=project_id)
            )

    @staticmethod
    def add_documents(project_id: int, user: User, documents: List[Dict[str, str]]):

        project = ProjectService.get_project(pk=project_id, owner=user, as_dict=False)
        if not project:
            raise ObjectDoesNotExist()
        existing_document_titles = {document.title for document in project.document_set.all()}
        documents = [document for document in documents if document["title"] not in existing_document_titles]

        if len(documents) + len(existing_document_titles) > 5000:
            raise PermissionDenied("You are only allowed to have 5,000 documents in a single project.")

        for document in documents:
            project.document_set.create(**document)

        DocumentService.__set_redis_project_cache(project)

    @staticmethod
    def update_document(
        document_id: int,
        project_id: int,
        user: Optional[User] = None,
        label: Optional[int] = None,
        order: Optional[int] = None,
    ) -> None:
        document = Document.objects.get(pk=document_id, project__pk=project_id)
        if user and document.project.owner != user:
            raise ObjectDoesNotExist()
        if label is not None:
            document.label = label
            document.labeled_date = datetime.utcnow()
        if order is not None:
            document.order = order
        document.save()

        if label is not None:
            name = f"project:{project_id}"
            if not redis_client.hexists(name, "total_documents"):
                DocumentService.__set_redis_project_cache(ProjectService.get_project(id=project_id))
            if label == 1:
                redis_client.hincrby(name, "positive_labels")
            else:
                redis_client.hincrby(name, "negative_labels")
            kafka_producer.produce(topic="project", key=project_id, value=redis_client.hgetall(name))
