import unittest
from app.mcp_contract import REGISTER_REPORT_TOOL

class MCPContractTests(unittest.TestCase):
    def test_name(self):
        self.assertEqual(REGISTER_REPORT_TOOL['name'], 'registrar_reporte')

    def test_required_consent(self):
        schema = REGISTER_REPORT_TOOL['inputSchema']
        self.assertIn('consent', schema['required'])
        self.assertIn('idempotency_key', schema['required'])
        self.assertEqual(schema['properties']['consent']['enum'], ['yes'])

    def test_no_extra_fields(self):
        self.assertFalse(REGISTER_REPORT_TOOL['inputSchema']['additionalProperties'])

if __name__ == '__main__':
    unittest.main()
