FROM python:3.9.6-alpine
LABEL Description="This container is used to start the document ordering service."
WORKDIR /opt/orderservice

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Dependencies
RUN apk update \
    && apk add postgresql-dev build-base python3-dev musl-dev librdkafka-dev py3-scipy
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt


COPY ./src/main/*.py .

CMD python estimatorservice.py