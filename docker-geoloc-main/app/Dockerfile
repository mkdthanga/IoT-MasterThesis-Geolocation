FROM python:3.8.1-alpine3.11

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV PROJ_DIR=/usr

RUN addgroup -S appuser ; adduser -S appuser -G appuser -h /app ;\
    chown appuser:appuser /app

WORKDIR /app
COPY --chown=appuser:appuser / /app

RUN apk update \
    && apk add --upgrade --no-cache \
	    python3 libpq uwsgi-python3 \
		python3-dev py3-pip alpine-sdk postgresql-dev postgresql \
		proj proj-dev \
		proj-util \
        bash openssh curl ca-certificates openssl less htop \
		g++ make wget rsync \
        build-base libpng-dev freetype-dev libexecinfo-dev openblas-dev libgomp lapack-dev \
		libgcc libquadmath musl  \
		libgfortran \
		lapack-dev \
	&&  pip install --no-cache-dir --upgrade pip \
    &&  pip install --no-cache-dir -r requirements.txt


CMD ["top"]