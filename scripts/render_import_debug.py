import os
import traceback

print("RENDER_IMPORT_DEBUG_START", flush=True)
print("APP_ENV=", os.getenv("APP_ENV"), flush=True)
print("DEBUG=", os.getenv("DEBUG"), flush=True)
print("ENABLE_DEV_ENDPOINTS=", os.getenv("ENABLE_DEV_ENDPOINTS"), flush=True)
print("PYTHON_VERSION=", os.getenv("PYTHON_VERSION"), flush=True)
print("CORS_ORIGINS=", os.getenv("CORS_ORIGINS"), flush=True)
print("DATABASE_URL_SET=", bool(os.getenv("DATABASE_URL")), flush=True)
print("SECRET_KEY_SET=", bool(os.getenv("SECRET_KEY")), flush=True)

try:
    print("IMPORT_CONFIG", flush=True)
    from app.core.config import settings
    print("CONFIG_OK", flush=True)

    print("IMPORT_ROUTER", flush=True)
    from app.api.router import router
    print("ROUTER_OK", flush=True)

    print("IMPORT_MAIN", flush=True)
    from app.main import app
    print("IMPORT_OK", flush=True)
except BaseException as e:
    print("IMPORT_FAILED", type(e).__name__, str(e), flush=True)
    traceback.print_exc()
    raise
