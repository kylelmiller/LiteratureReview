#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

#python manage.py migrate

# docker-compose exec literature-review python manage.py flush --no-input
# docker-compose exec literature-review python manage.py migrate
# docker-compose exec literature-review python manage.py createsuperuser

exec "$@"