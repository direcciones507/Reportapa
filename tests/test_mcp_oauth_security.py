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

    @patch("app.mcp_oauth.jwt.decode", return_value={
        "sub": "auth0|operator", "scope": "reportapa:reports:create"
    })
    @patch("app.mcp_oauth.PyJWKClient")
    @patch("app.mcp_oauth.jwt.get_unverified_header", return_value={"alg": "RS256"})
    def test_preserves_auth0_issuer_trailing_slash(self, _header, jwks, decode):
        jwks.return_value.get_signing_key_from_jwt.return_value.key = "mock-key"
        issuer = "https://example.us.auth0.com/"
        with patch.dict(os.environ, {
            "REPORTAPA_OAUTH_ISSUER": issuer,
            "REPORTAPA_OAUTH_AUDIENCE": "https://reportapa.online/mcp",
            "REPORTAPA_OAUTH_JWKS_URL": issuer + ".well-known/jwks.json",
            "REPORTAPA_OAUTH_ALLOWED_SUB": "auth0|operator",
        }):
            verify_mcp_access_token("mock-token")
        self.assertEqual(decode.call_args.kwargs["issuer"], issuer)

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
