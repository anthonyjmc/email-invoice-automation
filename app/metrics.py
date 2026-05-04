"""
Prometheus metrics: request counts (by status class) and latency histograms.
Scrape GET /metrics when OBSERVABILITY_METRICS_ENABLED=true (protect the endpoint in production).
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_LATENCY = Histogram(
    "http_server_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

REQUEST_TOTAL = Counter(
    "http_server_requests_total",
    "Total HTTP requests",
    ("method", "route", "status_class"),
)


def http_status_class(status_code: int) -> str:
    if status_code < 200:
        return "1xx"
    if status_code < 300:
        return "2xx"
    if status_code < 400:
        return "3xx"
    if status_code < 500:
        return "4xx"
    return "5xx"


def record_http_request(*, method: str, route: str, status_code: int, duration_s: float) -> None:
    cls = http_status_class(status_code)
    REQUEST_TOTAL.labels(method=method, route=route, status_class=cls).inc()
    REQUEST_LATENCY.labels(method=method, route=route).observe(duration_s)


def render_metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
