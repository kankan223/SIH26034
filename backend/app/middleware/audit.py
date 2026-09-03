"""Audit middleware per prd.md §20.1.

Intercepts mutating HTTP operations (POST, PUT, PATCH, DELETE) and captures
contextual request details for audit logging. Does NOT log sensitive data
(auth credentials, raw binary images).
"""

import json
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.audit_service import log_action

# HTTP methods that are mutating
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to exclude from audit logging (health checks, docs, static files)
EXCLUDED_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}

# Sensitive headers to redact
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs audit events for mutating HTTP operations.

    This middleware:
    1. Intercepts POST, PUT, PATCH, DELETE requests
    2. Captures request path, method, status code, and duration
    3. Extracts user ID from JWT if present (without validating)
    4. Logs the audit event to the audit_logs table
    5. Does NOT log sensitive data (auth headers, binary payloads)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-mutating methods
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Skip health check and docs paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        # Capture start time
        start_time = time.time()

        # Extract request context (before processing)
        request_id = str(uuid.uuid4())
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        # Try to extract user ID from Authorization header (best effort, no validation)
        actor_id = self._extract_actor_id(request)

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Determine entity type and action from path
        entity_type, entity_id = self._extract_entity_info(path, request)

        # Build the audit log entry
        action = self._determine_action(method, path)
        after_value = {
            "status_code": response.status_code,
            "method": method,
            "path": path,
            "duration_ms": duration_ms,
            "request_id": request_id,
            "client_ip": client_ip,
        }

        # Log the audit event (non-blocking, best effort)
        try:
            await log_action(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                after_value=after_value,
            )
        except Exception:
            # Don't let audit logging failures break the request
            pass

        return response

    def _extract_actor_id(self, request: Request) -> str | None:
        """Extract user ID from Authorization header (best effort).

        This does NOT validate the token — it just tries to decode the JWT
        payload to get the user ID. If it fails, returns None.
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        try:
            # Simple base64 decode of JWT payload (no validation)
            import base64
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Decode the payload (second part)
            payload = parts[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            return data.get("sub")  # "sub" claim contains user ID
        except Exception:
            return None

    def _extract_entity_info(self, path: str, request: Request) -> tuple[str, str]:
        """Extract entity type and ID from the request path."""
        parts = path.strip("/").split("/")

        # Pattern: /api/v1/inspections/{id}/images
        if len(parts) >= 4 and parts[2] == "inspections":
            if len(parts) >= 5 and parts[4] == "images":
                return "image", parts[3] if len(parts) > 3 else "unknown"
            if len(parts) >= 4:
                return "inspection", parts[3] if len(parts) > 3 else "unknown"

        # Pattern: /api/v1/rules/{id}
        if len(parts) >= 4 and parts[2] == "rules":
            return "rule", parts[3] if len(parts) > 3 else "unknown"

        # Pattern: /api/v1/corrections/{id}
        if len(parts) >= 4 and parts[2] == "corrections":
            return "correction", parts[3] if len(parts) > 3 else "unknown"

        # Default
        return "unknown", "unknown"

    def _determine_action(self, method: str, path: str) -> str:
        """Determine the action type from HTTP method and path."""
        if method == "POST":
            if "/images" in path:
                return "upload_image"
            return "create"
        elif method == "PUT":
            return "update"
        elif method == "PATCH":
            return "update"
        elif method == "DELETE":
            return "delete"
        return "unknown"
