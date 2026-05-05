import asyncio

from fastapi import FastAPI
from fastapi import Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import MetricsMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.schemas.common import HealthResponse
from app.services.mobile_event_stream_service import mobile_event_stream_service
from app.services.sensor_data_autogen_service import sensor_data_autogen_service
from app.services.task_stream_service import task_stream_service

setup_logging()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)


@app.exception_handler(OperationalError)
async def db_unavailable_handler(_: Request, __: OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="API documentation",
        routes=app.routes,
    )
    components = openapi_schema.setdefault("components", {})
    components["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "security" in operation:
                operation["security"] = [{"BearerAuth": []}]

    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
async def startup_tasks() -> None:
    loop = asyncio.get_running_loop()
    task_stream_service.bind_event_loop(loop)
    mobile_event_stream_service.bind_event_loop(loop)
    if settings.sensor_autogen_enabled and (settings.sensor_source_mode == "fake_only" or settings.debug):
        await sensor_data_autogen_service.start()


@app.on_event("shutdown")
async def shutdown_tasks() -> None:
    if sensor_data_autogen_service.is_running:
        await sensor_data_autogen_service.stop()


@app.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    summary="Application Health Check",
    description="Returns the public health status of the API service.",
)
def root_health() -> HealthResponse:
    return HealthResponse(status="ok", service="sports-facility-api")


@app.get(
    "/",
    tags=["health"],
    response_model=HealthResponse,
    summary="Root Health Check",
    description="Returns the public health status of the API service root endpoint.",
)
def root_index_health() -> HealthResponse:
    return HealthResponse(status="ok", service="sports-facility-api")


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html() -> HTMLResponse:
    swagger_ui = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
    )
    custom_css = """
    <style>
      .curl-command { display: none !important; }
      .curl-command + div { display: none !important; }
    </style>
    """
    html = swagger_ui.body.decode("utf-8").replace("</head>", f"{custom_css}</head>")
    return HTMLResponse(content=html, status_code=swagger_ui.status_code)


app.include_router(router)
