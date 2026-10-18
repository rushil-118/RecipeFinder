FROM python:3.12-slim AS build
WORKDIR /w
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
ARG VERSION=dev
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="recipe-finder" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"

RUN groupadd -g 10001 app && useradd -u 10001 -g app -M -s /usr/sbin/nologin app
COPY --from=build /install /usr/local
WORKDIR /app
COPY recipefinder ./recipefinder

ENV APP_VERSION=${VERSION} GIT_SHA=${GIT_SHA} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", \
     "--graceful-timeout", "20", "--worker-tmp-dir", "/dev/shm", "recipefinder.api:create_app()"]
