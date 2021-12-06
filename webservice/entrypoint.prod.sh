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

# docker-compose -f docker-compose.prod.yml exec literature-review python manage.py flush --no-input
# docker-compose -f docker-compose.prod.yml exec literature-review python manage.py migrate
# docker-compose -f docker-compose.prod.yml exec literature-review python manage.py createsuperuser
# docker-compose -f docker-compose.prod.yml exec literature-review python manage.py collectstatic --no-input --clear

exec "$@"