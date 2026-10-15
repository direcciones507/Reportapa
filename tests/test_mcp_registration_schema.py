import unittest
from app.mcp_contract import REGISTER_REPORT_TOOL


class MCPRegistrationSchemaTests(unittest.TestCase):
    def test_registration_fields(self):
        schema = REGISTER_REPORT_TOOL["inputSchema"]
        self.assertEqual(schema["properties"]["consent"]["enum"], ["yes"])
        self.assertIn("idempotency_key", schema["required"])
        self.assertIn("needs", schema["required"])
        self.assertFalse(schema["additionalProperties"])

    def test_single_write_tool(self):
        self.assertEqual(REGISTER_REPORT_TOOL["name"], "registrar_reporte")


if __name__ == "__main__":
    unittest.main()
