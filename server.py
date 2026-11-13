"""Aegis Intelligence - HTTP Server Engine

Localhost-only HTTP service binding to 127.0.0.1:8765, providing authenticated
API access, request size guards, structured error handling, and thread concurrency.
"""

import os
import sys
import uuid
import json
import signal
import logging
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from storage.database import init_db
from security.authentication import authenticate_request, AuthenticationError
from security.path_validator import PathValidationError
from security.approvals import ApprovalRequiredException
from security.audit_log import log_audit
from api.routes import router
from api.responses import error_response, success_response
from api.schemas import ValidationError

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("aegis.server")

# Routes permitted without authentication for local health monitoring
PUBLIC_PATHS = {"/health", "/openapi.json"}

class AegisRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests with authentication, size limit, and routing."""

    server_version = "AegisIntelligence/1.0"

    def log_message(self, format, *args):
        """Route internal server messages to standard logger."""
        logger.debug("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    def send_json_response(self, status_code: int, body_bytes: bytes):
        """Send formatted HTTP headers and JSON payload."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body_bytes)

    def read_request_body(self, request_id: str) -> Optional[dict]:
        """Read and parse JSON body with strict size limit guard."""
        content_length_header = self.headers.get("Content-Length")
        if not content_length_header:
            return {}

        try:
            content_length = int(content_length_header)
        except ValueError:
            return None

        if content_length > Config.MAX_REQUEST_BODY_BYTES:
            raise ValueError(f"Request body exceeds maximum size of {Config.MAX_REQUEST_BODY_BYTES} bytes.")

        if content_length <= 0:
            return {}

        raw_bytes = self.rfile.read(content_length)
        if not raw_bytes:
            return {}

        try:
            return json.loads(raw_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in request body: {e}")

    def dispatch_request(self, method: str):
        """Core dispatch logic for GET, POST, PUT, DELETE."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path
        query_params = urllib.parse.parse_qs(url_parsed.query)

        # 1. Localhost enforcement check
        if client_ip not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(f"Rejected non-localhost request from IP: {client_ip}")
            code, resp = error_response("FORBIDDEN", "Aegis Intelligence accepts localhost connections only.", request_id, 403)
            self.send_json_response(code, resp)
            return

        # 2. Authentication check
        if path not in PUBLIC_PATHS:
            try:
                authenticate_request(dict(self.headers))
            except AuthenticationError as auth_err:
                log_audit(
                    action="AUTH_FAILED",
                    actor="anonymous",
                    resource_type="api",
                    resource_id=path,
                    status="FAILED",
                    details={"error": str(auth_err)},
                    request_id=request_id,
                    ip=client_ip
                )
                code, resp = error_response("UNAUTHORIZED", str(auth_err), request_id, 401)
                self.send_json_response(code, resp)
                return

        # 3. Read Body (for POST, PUT, PATCH, DELETE)
        body = {}
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body = self.read_request_body(request_id)
                if body is None:
                    code, resp = error_response("BAD_REQUEST", "Invalid Content-Length header.", request_id, 400)
                    self.send_json_response(code, resp)
                    return
            except ValueError as ve:
                code, resp = error_response("BAD_REQUEST", str(ve), request_id, 400)
                self.send_json_response(code, resp)
                return

        request_context = {
            "method": method,
            "path": path,
            "query_params": query_params,
            "headers": dict(self.headers),
            "body": body,
            "request_id": request_id,
            "client_ip": client_ip
        }

        # 4. Route resolution
        resolved = router.resolve(method, path)
        if not resolved:
            code, resp = error_response("NOT_FOUND", f"Endpoint '{method} {path}' not found.", request_id, 404)
            self.send_json_response(code, resp)
            return

        handler_func, path_kwargs = resolved

        # 5. Handler execution with error shielding
        try:
            status_code, response_bytes = handler_func(request_context, path_kwargs)
            self.send_json_response(status_code, response_bytes)
        except ValidationError as ve:
            code, resp = error_response("VALIDATION_ERROR", str(ve), request_id, 400)
            self.send_json_response(code, resp)
        except PathValidationError as pve:
            code, resp = error_response("PATH_TRAVERSAL_DETECTED", str(pve), request_id, 403)
            self.send_json_response(code, resp)
        except ApprovalRequiredException as are:
            code, resp = error_response(
                code="APPROVAL_REQUIRED",
                message=str(are),
                request_id=request_id,
                status_code=403
            )
            self.send_json_response(code, resp)
        except PermissionError as pe:
            code, resp = error_response("PERMISSION_DENIED", str(pe), request_id, 403)
            self.send_json_response(code, resp)
        except FileNotFoundError as fnfe:
            code, resp = error_response("NOT_FOUND", str(fnfe), request_id, 404)
            self.send_json_response(code, resp)
        except KeyError as ke:
            code, resp = error_response("BAD_REQUEST", f"Missing required parameter: {ke}", request_id, 400)
            self.send_json_response(code, resp)
        except ValueError as ve:
            code, resp = error_response("BAD_REQUEST", str(ve), request_id, 400)
            self.send_json_response(code, resp)
        except Exception as exc:
            logger.exception(f"Unhandled server error on {method} {path} [{request_id}]: {exc}")
            # Shield internal stack trace from external caller
            code, resp = error_response("INTERNAL_ERROR", "An internal server error occurred.", request_id, 500)
            self.send_json_response(code, resp)

    def do_GET(self):
        self.dispatch_request("GET")

    def do_POST(self):
        self.dispatch_request("POST")

    def do_PUT(self):
        self.dispatch_request("PUT")

    def do_DELETE(self):
        self.dispatch_request("DELETE")

    def do_OPTIONS(self):
        # Localhost CORS preflight support
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5678")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Aegis-Token")
        self.end_headers()

def run_server():
    """Initialize database and start the HTTP service."""
    logger.info("Initializing Aegis database storage...")
    init_db()
    Config.load_api_token()

    server_address = (Config.HOST, Config.PORT)
    httpd = ThreadingHTTPServer(server_address, AegisRequestHandler)

    logger.info(f"🛡️  Aegis Intelligence Backend listening on http://{Config.HOST}:{Config.PORT}")
    logger.info("🔑 API Authentication configured successfully (token length: %d)", len(Config.API_TOKEN))
    logger.info("Press Ctrl+C to terminate.")

    def handle_sig(sig, frame):
        logger.info("Shutting down Aegis Intelligence gracefully...")
        httpd.server_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        logger.info("Aegis Intelligence stopped.")

if __name__ == "__main__":
    run_server()
