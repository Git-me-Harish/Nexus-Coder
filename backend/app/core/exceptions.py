"""
Global exception handling — also responsible for matching the frontend's
expected error envelope `{ error: { code, message } }` (see client.ts:
`err?.error?.message`), instead of FastAPI's default `{ detail: ... }`.

Route code raises HTTPException(status, {"code": "...", "message": "..."})
— `detail` is a dict, and this handler unwraps it into the envelope.
Falling back to a generic code if detail is a plain string keeps this safe
even where a route or a library raises a bare HTTPException.
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("nexus")


def api_error(status_code: int, code: str, message: str | None = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message or code})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            body = {"error": exc.detail}
        else:
            body = {"error": {"code": "ERROR", "message": str(exc.detail)}}
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_INPUT", "message": str(exc.errors()[0].get("msg", "Invalid input"))}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}})
