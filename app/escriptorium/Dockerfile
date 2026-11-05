FROM docker.io/library/node:20-bookworm-slim AS frontend

WORKDIR /build
COPY ./front /build
RUN apt-get update -q && \
    apt-get install -y --no-install-recommends gettext && \
    rm -rf /var/lib/apt/lists/*
RUN npm ci && npm run production

FROM docker.io/library/python:3.12-slim-bookworm

ENV FRONTEND_DIR=/usr/src/app/front
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

WORKDIR /usr/src/app

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends \
      build-essential curl gettext git libglib2.0-0 libjpeg62-turbo \
      libpq-dev libvips-dev netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY ./app/entrypoint.sh /usr/src/app/entrypoint.sh
COPY ./app/manage.py /usr/src/app/manage.py
COPY ./app/requirements.txt /usr/src/app/requirements.txt
COPY ./app/uwsgi.ini /usr/src/app/uwsgi.ini

COPY ./app/apps /usr/src/app/apps
COPY ./app/escriptorium /usr/src/app/escriptorium
COPY ./app/locale /usr/src/app/locale
COPY ./app/homepage /usr/src/app/homepage
COPY ./app/contributors /usr/src/app/contributors
COPY --from=frontend /build/dist /usr/src/app/front

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /usr/src/app/requirements.txt
RUN python manage.py compilemessages

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
