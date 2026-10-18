"""HTTP API over the same Catalog the command-line program uses."""
import json
import os
import time
import uuid
from datetime import UTC, datetime

from flask import Flask, Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    disable_created_metrics,
    generate_latest,
)

from recipefinder.catalog import DEFAULT_DATA, Catalog, load_recipes

disable_created_metrics()
NOISY_ROUTES = {"/health", "/ready", "/metrics"}


def log(level, msg, **fields):
    """One JSON object per line on stdout, so any log pipeline can parse it."""
    record = {"ts": datetime.now(UTC).isoformat(), "level": level, "msg": msg}
    record.update(fields)
    print(json.dumps(record), flush=True)


def _flag(value):
    return str(value).strip().lower() == "true"


def create_app(config=None, catalog=None):
    cfg = {
        "DATA_PATH": os.environ.get("DATA_PATH", str(DEFAULT_DATA)),
        "APP_VERSION": os.environ.get("APP_VERSION", "dev"),
        "GIT_SHA": os.environ.get("GIT_SHA", "unknown"),
        "FEATURE_NUTRITION": os.environ.get("FEATURE_NUTRITION", "true"),
        "FAIL_HEALTH": os.environ.get("FAIL_HEALTH", "false"),
    }
    cfg.update(config or {})

    app = Flask(__name__)
    app.config.update(cfg)
    catalog = catalog if catalog is not None else Catalog(load_recipes(cfg["DATA_PATH"]))
    nutrition_on = _flag(cfg["FEATURE_NUTRITION"])

    registry = CollectorRegistry()
    requests_total = Counter(
        "http_requests_total", "HTTP requests handled.", ["method", "route", "status"], registry=registry)
    request_seconds = Histogram(
        "http_request_duration_seconds", "HTTP request latency.", ["route"], registry=registry)
    Gauge("recipes_loaded", "Recipes in the in-memory catalog.", registry=registry).set(len(catalog))
    Gauge("feature_enabled", "1 if a feature flag is on.", ["feature"], registry=registry
          ).labels("nutrition").set(1 if nutrition_on else 0)
    Gauge("build_info", "Running build (value is always 1).", ["version", "commit"], registry=registry
          ).labels(cfg["APP_VERSION"], cfg["GIT_SHA"]).set(1)

    @app.before_request
    def start_request():
        g.start = time.perf_counter()
        supplied = request.headers.get("X-Request-Id", "")
        g.request_id = supplied if 0 < len(supplied) <= 128 else str(uuid.uuid4())

    @app.after_request
    def finish_request(response):
        route = request.url_rule.rule if request.url_rule else "unmatched"
        elapsed = time.perf_counter() - g.get("start", time.perf_counter())
        requests_total.labels(request.method, route, str(response.status_code)).inc()
        request_seconds.labels(route).observe(elapsed)
        response.headers["X-Request-Id"] = g.get("request_id", "")
        if route not in NOISY_ROUTES or response.status_code >= 400:
            parts = request.headers.get("traceparent", "").split("-")
            log("info", "request", method=request.method, route=route, status=response.status_code,
                duration_ms=round(elapsed * 1000), request_id=g.get("request_id", ""),
                trace_id=parts[1] if len(parts) >= 4 else "")
        return response

    def need(name):
        value = request.args.get(name, "").strip()
        if not value:
            return None, (jsonify(error=f"query parameter '{name}' is required"), 400)
        return value, None

    @app.get("/health")
    def health():
        """Liveness: can the process answer?"""
        if _flag(app.config["FAIL_HEALTH"]):
            return "unhealthy\n", 500
        return "ok\n"

    @app.get("/ready")
    def ready():
        """Readiness: the catalog loaded at least one recipe."""
        return ("ready\n", 200) if len(catalog) > 0 else ("catalog is empty\n", 503)

    @app.get("/version")
    def version():
        return jsonify(version=app.config["APP_VERSION"], commit=app.config["GIT_SHA"])

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/recipes/cuisines")
    def cuisines():
        return jsonify(cuisines=catalog.cuisines())

    @app.get("/recipes/count")
    def count():
        cuisine, err = need("cuisine")
        return err or jsonify(cuisine=cuisine, count=catalog.count_by_cuisine(cuisine))

    @app.get("/recipes/names")
    def names():
        cuisine, err = need("cuisine")
        return err or jsonify(cuisine=cuisine, names=catalog.names_by_cuisine(cuisine))

    @app.get("/recipes/quick")
    def quick():
        raw, err = need("max_minutes")
        if err:
            return err
        try:
            limit = int(raw)
        except ValueError:
            return jsonify(error="max_minutes must be an integer"), 400
        if not 1 <= limit <= 1000:
            return jsonify(error="max_minutes must be between 1 and 1000"), 400
        veg = request.args.get("vegetarian", "false").strip().lower()
        if veg not in ("true", "false"):
            return jsonify(error="vegetarian must be true or false"), 400
        found = catalog.quick(limit, veg == "true")
        return jsonify(recipes=[
            {"name": r.name, "cuisine": r.cuisine, "minutes": r.minutes,
             "calories": r.calories, "vegetarian": r.vegetarian} for r in found])

    @app.get("/recipes/calories")
    def calories():
        if not nutrition_on:
            return jsonify(error="nutrition lookup is disabled"), 403
        cuisine, err = need("cuisine")
        if err:
            return err
        average = catalog.average_calories(cuisine)
        if average is None:
            return jsonify(error=f"no recipes for cuisine '{cuisine}'"), 404
        return jsonify(cuisine=cuisine, average_calories=average)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify(error="method not allowed"), 405

    @app.errorhandler(500)
    def server_error(e):
        log("error", "unhandled error", request_id=g.get("request_id", ""), error=repr(e))
        return jsonify(error="internal error"), 500

    return app
