# Literature Review

The purpose of this project is to ease the task of literature reviews. It uses logistic regression to order unseen
documents and predict the number of remaining documents that would be included in the unlabeled set. The thought is that
you can stop a literature review early while still including the vast majority of documents that should be included.
There are other similar tasks this could assist with like the discovery phase of court proceedings.

It uses the Django framework for the UI and ORM, gunicorn WSGI and nginx. This project is also vertically and 
horizontally scalable. It uses redis to front the postgres database and kafka as communication between labeling and 
the document ordering and estimation services. Postgres can be scaled through read replicas and the project is 
stateless so the application service can be horizontally scaled as well.

## Prerequisites
1. Install docker and docker compose
2. python 3.9 and python3-pip

## Getting Started
1. `LiteratureReview/webservice/src/main/litreviewapi$ python3 manage.py makemigrations`
2. `LiteratureReview$ docker-compose up`
3. `LiteratureReview$ docker-compose exec literature-review python manage.py migrate`
4. `LiteratureReview$ docker-compose exec literature-review python manage.py createsuperuser` to make an admin/admin superuser. If you change the password you will need to change in the services config. They use an admin account update different projects' document order and estimated remaining positive documents.
5. Navigate to `localhost:8000`

