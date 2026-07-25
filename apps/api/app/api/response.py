from typing import Any

from fastapi import Request

API_VERSION = "v1"


def response_meta(request: Request) -> dict[str, Any]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "api_version": API_VERSION,
    }


def ok(request: Request, data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "meta": response_meta(request)}


def error_body(request: Request, code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "meta": response_meta(request),
    }
