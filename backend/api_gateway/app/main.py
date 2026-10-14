from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import httpx, os, time
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from shared.logging_utils import get_logger, new_request_id, request_id_ctx

logger = get_logger("gateway")

app = FastAPI(title="Allamni API Gateway", version="1.0.0")
_cors_regex = os.getenv("CORS_ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS","http://localhost:8080").split(","),
    allow_origin_regex=_cors_regex,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

RATE_LIMIT = int(os.getenv("GATEWAY_RATE_LIMIT", "300"))
RATE_WINDOW = 60.0
_BUCKETS: dict[str, list] = {}


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    request_id_ctx.set(request_id)
    start = time.monotonic()
    try:
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            f"access: {request.method} {request.url.path} -> {response.status_code} in {duration_ms:.1f}ms",
            extra={"fields": {"http.method": request.method, "http.path": request.url.path,
                              "http.status": response.status_code, "duration_ms": round(duration_ms, 1)}},
        )
        return response
    except Exception:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception(
            f"access: {request.method} {request.url.path} failed in {duration_ms:.1f}ms",
            extra={"fields": {"http.method": request.method, "http.path": request.url.path,
                              "duration_ms": round(duration_ms, 1)}},
        )
        raise


@app.middleware("http")
async def gateway_rate_limit(request: Request, call_next):
    if request.url.path != "/health":
        now = time.monotonic()
        client = request.client.host if request.client else "local"
        bucket = _BUCKETS.get(client)
        if bucket is None or now >= bucket[1]:
            bucket = [[now], now + RATE_WINDOW]
            _BUCKETS[client] = bucket
        else:
            bucket[0].append(now)
        cutoff = now - RATE_WINDOW
        bucket[0] = [t for t in bucket[0] if t >= cutoff][- (RATE_LIMIT + 20):]
        if len(_BUCKETS) > 2000:
            _BUCKETS.pop(next(iter(_BUCKETS)))
        if len(bucket[0]) > RATE_LIMIT:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)

TARGETS = {
    "auth": os.getenv("AUTH_URL","http://localhost:8001"),
    "learning": os.getenv("LEARNING_URL","http://localhost:8002"),
    "ai": os.getenv("AI_URL","http://localhost:8003"),
    "integration": os.getenv("INTEGRATION_URL","http://localhost:8004"),
    "institution": os.getenv("INSTITUTION_URL","http://localhost:8005"),
}

@app.get("/health")
def health():
    return {"status":"ok","service":"gateway","targets":list(TARGETS)}

async def proxy(request: Request, target: str, prefix: str):
    path = request.url.path[len(prefix):] or "/"
    url = TARGETS[target] + path
    if request.url.query:
        url += "?" + request.url.query
    body = await request.body()
    headers = {k:v for k,v in request.headers.items() if k.lower() not in {"host","content-length"}}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.request(request.method, url, content=body, headers=headers)
    return Response(content=r.content, status_code=r.status_code,
                    headers={"content-type":r.headers.get("content-type","application/json")})

def register(prefix,target):
    async def handler(request: Request):
        return await proxy(request,target,prefix)
    app.add_api_route(prefix+"/{path:path}",handler,
                      methods=["GET","POST","PUT","PATCH","DELETE"],
                      include_in_schema=False)

register("/api/auth","auth")
register("/api/learning","learning")
register("/api/ai","ai")
register("/api/institution","institution")
register("/api/integration","integration")
