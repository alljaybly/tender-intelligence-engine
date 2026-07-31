from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import logging
import os

from .routes import router as api_router
from .utils import error_response
from .services.database import init_db



app = FastAPI(
    title='Tender Engine API',
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True
    }
)

# -------------------------------
# CORS CONFIGURATION
# -------------------------------
origins = [
    "http://localhost:5173",    
    "http://localhost:3000",
    "https://tender-intelligence-engine.netlify.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

# -------------------------------
# Startup Event: Initialize DB
# -------------------------------
@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("[DB] Database initialized on startup")

# -------------------------------
# /api/health Endpoint (public)
# -------------------------------
@app.get("/api/health")
async def root_health():
    return JSONResponse({'status': 'ok', 'services': ['extract', 'validate', 'price', 'doc']})

# -------------------------------
# Error Handlers
# -------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else 'Request failed'
    code = 'http_error'
    if exc.status_code == 404:
        code = 'not_found'
    elif exc.status_code == 401:
        code = 'unauthorized'
    elif exc.status_code == 403:
        code = 'forbidden'
    elif exc.status_code == 429:
        code = 'rate_limit_exceeded'
        message = 'Too many requests'
    return error_response(code, message, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = exc.errors()[0].get('msg', 'Invalid request') if exc.errors() else 'Invalid request'
    return error_response('validation_error', message, 422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("[ERROR] Unhandled exception: %s", exc)
    return error_response('internal_server_error', 'Internal server error', 500)

# -------------------------------
# Include all routers with /api prefix
# -------------------------------
app.include_router(api_router, prefix="/api")

# -------------------------------
# Frontend (index.html)
# -------------------------------
@app.get("/")
async def serve_frontend():
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(os.path.join(static_dir, "index.html")):
        return FileResponse(os.path.join(static_dir, "index.html"))
    return {"message": "Tender Engine API is running"}

# -------------------------------
# Logging Setup
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tender-engine-api')
