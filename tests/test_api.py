"""Aegis Intelligence - API & Routing Tests"""

import os
import sys
import json
import unittest
import urllib.request
import urllib.error
import threading
from http.server import ThreadingHTTPServer

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from storage.database import init_db
from server import AegisRequestHandler

TEST_PORT = 8799
TEST_TOKEN = "test_secret_token_12345"

class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test environment
        Config.HOST = "127.0.0.1"
        Config.PORT = TEST_PORT
        Config.API_TOKEN = TEST_TOKEN
        init_db()

        cls.server = ThreadingHTTPServer((Config.HOST, TEST_PORT), AegisRequestHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{TEST_PORT}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, path: str, method: str = "GET", body: dict = None, headers: dict = None):
        url = f"{self.base_url}{path}"
        req_headers = headers if headers is not None else {"Authorization": f"Bearer {TEST_TOKEN}"}
        req_headers["Content-Type"] = "application/json"

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                content = json.loads(resp.read().decode("utf-8"))
                return status, content
        except urllib.error.HTTPError as e:
            content = json.loads(e.read().decode("utf-8"))
            return e.code, content

    def test_health_check_unauthenticated(self):
        """Health check endpoint should succeed without auth headers."""
        status, body = self._request("/health", headers={})
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIsNotNone(body["request_id"])
        self.assertEqual(body["data"]["status"], "healthy")
        self.assertIsNone(body["error"])

    def test_openapi_schema(self):
        """OpenAPI spec endpoint should return valid schema."""
        status, body = self._request("/openapi.json", headers={})
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("paths", body["data"])

    def test_unauthorized_request(self):
        """Protected endpoint without token should return 401."""
        status, body = self._request("/api/v1/projects", headers={})
        self.assertEqual(status, 401)
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "UNAUTHORIZED")

    def test_invalid_token(self):
        """Protected endpoint with invalid token should return 401."""
        status, body = self._request("/api/v1/projects", headers={"X-Aegis-Token": "bad_token"})
        self.assertEqual(status, 401)
        self.assertFalse(body["success"])

    def test_valid_token_authenticated(self):
        """Protected endpoint with valid token should return 200."""
        status, body = self._request("/api/v1/projects")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIsInstance(body["data"], list)

    def test_not_found_route(self):
        """Non-existent route should return structured 404."""
        status, body = self._request("/api/v1/non_existent_route")
        self.assertEqual(status, 404)
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

if __name__ == "__main__":
    unittest.main()
