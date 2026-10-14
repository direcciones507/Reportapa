"""OAuth operator isolation tests. No external identity provider or production secrets."""
import os
import unittest
from unittest.mock import patch
from jwt.exceptions import InvalidTokenError
from app.mcp_oauth import verify_mcp_access_token


class OAuthOperatorTests(unittest.TestCase):
    def test_missing_provider_configuration_fails_closed(self):
        with patch.dict(os.environ, {"REPORTAPA_OAUTH_ISSUER": "",
                                      "REPORTAPA_OAUTH_AUDIENCE": "",
                                      "REPORTAPA_OAUTH_JWKS_URL": ""}):
            with self.assertRaises(RuntimeError):
                verify_mcp_access_token("not-a-token")

    def test_rejects_insecure_jwks_endpoint(self):
        with patch.dict(os.environ, {
            "REPORTAPA_OAUTH_ISSUER": "https://login.example.com",
            "REPORTAPA_OAUTH_AUDIENCE": "https://reportapa.online/mcp",
            "REPORTAPA_OAUTH_JWKS_URL": "http://login.example.com/keys",
            "REPORTAPA_OAUTH_ALLOWED_SUB": "operator",
        }):
            with self.assertRaises(RuntimeError):
                verify_mcp_access_token("not-a-token")

    def test_rejects_missing_token(self):
        with patch.dict(os.environ, {
            "REPORTAPA_OAUTH_ISSUER": "https://login.example.com",
            "REPORTAPA_OAUTH_AUDIENCE": "https://reportapa.online/mcp",
            "REPORTAPA_OAUTH_JWKS_URL": "https://login.example.com/keys",
            "REPORTAPA_OAUTH_ALLOWED_SUB": "operator",
        }):
            with self.assertRaises(InvalidTokenError):
                verify_mcp_access_token("")


if __name__ == "__main__":
    unittest.main()
