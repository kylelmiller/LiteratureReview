from django.conf import settings
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=512)
    created_date = models.DateTimeField("date created", auto_now_add=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    estimated_positive = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.name


class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    source_id = models.CharField(max_length=128)
    title = models.CharField(max_length=512)
    journal = models.CharField(max_length=128, blank=True, null=True)
    publication_date = models.CharField(max_length=64, blank=True, null=True)
    authors = models.TextField(max_length=1024, blank=True, null=True)
    description = models.TextField(max_length=2048, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)
    label = models.IntegerField(blank=True, null=True)
    labeled_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.title
