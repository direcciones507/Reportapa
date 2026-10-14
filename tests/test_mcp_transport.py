"""Exercise MCP JSON-RPC end to end without touching the production database."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

AUTH = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}
REPORT = {
    "idempotency_key": "ea7a92c1-08a5-4a0e-a3bb-9cc59c63dcf1",
    "consent": "yes", "name": "Test Person", "phone": "66951426",
    "province": "Veraguas", "district": "Santiago",
    "township": "Santiago", "community": "Prueba",
    "damage": "Grietas en pared", "needs": ["Materiales para reparar la vivienda"]
}


class MCPTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def rpc(self, method, params=None, headers=None):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        return self.client.post("/mcp", json=payload, headers=headers or AUTH)

    def test_missing_auth_is_rejected(self):
        response = self.rpc("tools/list", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

    @patch("app.mcp_oauth.verify_mcp_access_token", return_value={"sub": "test"})
    def test_tool_discovery(self, _verify):
        response = self.rpc("tools/list")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["tools"][0]["name"], "registrar_reporte")

    @patch("app.mcp_oauth.verify_mcp_access_token", return_value={"sub": "test"})
    @patch("app.main.persist_report", return_value={"id": 12345})
    def test_register_returns_only_confirmed_id(self, persist, _verify):
        response = self.rpc("tools/call", {"name": "registrar_reporte", "arguments": REPORT})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["structuredContent"]["id"], 12345)
        persist.assert_called_once()

    @patch("app.mcp_oauth.verify_mcp_access_token", return_value={"sub": "test"})
    @patch("app.main.persist_report")
    def test_rejects_missing_consent_without_write(self, persist, _verify):
        response = self.rpc("tools/call", {"name": "registrar_reporte",
                                            "arguments": {**REPORT, "consent": "no"}})
        self.assertTrue(response.json()["result"]["isError"])
        persist.assert_not_called()

    @patch("app.mcp_oauth.verify_mcp_access_token", return_value={"sub": "test"})
    @patch("app.main.persist_report")
    def test_rejects_unknown_fields_without_write(self, persist, _verify):
        response = self.rpc("tools/call", {"name": "registrar_reporte",
                                            "arguments": {**REPORT, "admin": "true"}})
        self.assertEqual(response.json()["error"]["code"], -32602)
        persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
