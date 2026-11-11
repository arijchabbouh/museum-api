import logging
import time
import uuid
import os 

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from flask import Flask, g, jsonify, request
from pythonjsonlogger.json import JsonFormatter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logger = logging.getLogger("museum-api")
logger.handlers = [handler]
logger.setLevel(logging.INFO)
logger.propagate = False

provider = TracerProvider(resource=Resource.create({"service.name": "museum-api"}))
otlp = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp}/v1/traces")))
elif os.getenv("OTEL_CONSOLE") == "1":
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("museum-api")

app = Flask(__name__)

FlaskInstrumentor().instrument_app(app)
REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "endpoint"])
VISITS = Counter("museum_visits_total", "Visits logged", ["museum"])
@app.before_request
def start_timer():
    g.start = time.perf_counter()

@app.after_request
def log_request(response):
    duration = time.perf_counter() - g.start
    endpoint = request.url_rule.rule if request.url_rule else "unmatched"
    REQUESTS.labels(request.method, endpoint, response.status_code).inc()
    LATENCY.labels(request.method, endpoint).observe(duration)
    if endpoint != "/metrics":
        logger.info("request", extra={
            "method": request.method, "path": request.path,
            "status": response.status_code, "duration_ms": round(duration * 1000, 2),
        })
    return response

@app.errorhandler(Exception)
def handle_error(exc):
    if getattr(exc, "code", None):
        return jsonify(error=exc.name.lower()), exc.code
    logger.error("unhandled_error", exc_info=exc, extra={"path": request.path})
    return jsonify(error="internal server error"), 500

museums = {}
visits = []
POINTS_PER_VISIT = 10
BADGES = [(10, "gold"), (5, "silver"), (3, "bronze")]


def text(data, key, max_len=100):
    value = str(data.get(key, "")).strip()
    return value if 0 < len(value) <= max_len else ""


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/museums")
def list_museums():
    return jsonify(list(museums.values()))


@app.post("/museums")
def create_museum():
    data = request.get_json(silent=True) or {}
    name, theme, artist = text(data, "name"), text(data, "theme"), text(data, "artist", 50)
    if not name or not theme or not artist:
        return jsonify(error="'name', 'theme' and 'artist' are required"), 400
    museum = {"id": str(uuid.uuid4()), "name": name, "theme": theme, "artist": artist}
    museums[museum["id"]] = museum
    VISITS.labels(museum["name"]).inc()
    return jsonify(museum), 201


@app.get("/museums/<museum_id>")
def get_museum(museum_id):
    museum = museums.get(museum_id)
    if museum is None:
        return jsonify(error="museum not found"), 404
    return jsonify(museum)


@app.get("/artists/<artist>/museums")
def get_museums_by_artist(artist):
    own = [m for m in museums.values() if m["artist"].lower() == artist.lower()]
    return jsonify(own)


@app.post("/visits")
def create_visit():
    data = request.get_json(silent=True) or {}
    visitor = text(data, "visitor", 50)
    museum = museums.get(text(data, "museum_id"))
    if not visitor or not museum:
        return jsonify(error="'visitor' and a valid 'museum_id' are required"), 400
    already = any(v["visitor"].lower() == visitor.lower() and v["museum_id"] == museum["id"] for v in visits)
    is_owner = visitor.lower() == museum["artist"].lower()
    points = 0 if already or is_owner else POINTS_PER_VISIT
    with tracer.start_as_current_span("store_visit") as span:
        span.set_attribute("museum.id", museum["id"])
        visit = {"visitor": visitor, "museum_id": museum["id"], "artist": museum["artist"], "points": points}
        visits.append(visit) 
    return jsonify(visit), 201


def artist_profile(name):
    received = [v for v in visits if v["artist"].lower() == name.lower()]
    scoring = [v for v in received if v["points"] > 0]
    badge = next((b for n, b in BADGES if len(scoring) >= n), None)
    return {"artist": name, "visits": len(received), "points": sum(v["points"] for v in received), "badge": badge}


@app.get("/artists/<artist>")
def get_artist(artist):
    return jsonify(artist_profile(artist))


@app.get("/leaderboard")
def leaderboard():
    with tracer.start_as_current_span("compute_leaderboard"):
        names = {m["artist"] for m in museums.values()}
        board = sorted((artist_profile(n) for n in names), key=lambda p: p["points"], reverse=True)
    return jsonify(board[:10])

@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

def trace_id():
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)