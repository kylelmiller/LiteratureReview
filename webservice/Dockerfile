FROM python:3.9.6-alpine
LABEL Description="This container is used to start the literature review web service."
WORKDIR /opt/literaturereview

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Dependencies
RUN apk update \
    && apk add postgresql-dev build-base python3-dev musl-dev librdkafka-dev
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy entrypoint.sh
COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g' /opt/literaturereview/entrypoint.sh
RUN chmod +x /opt/literaturereview/entrypoint.sh

COPY ./src/main/litreviewapi/ .

# run entrypoint.sh
# ENTRYPOINT ["/opt/literaturereview/entrypoint.sh"]