"""OAuth access-token verification for the ReportaPA MCP resource server.

Never use REPORTAPA_INTEGRATION_TOKEN for this flow.
"""
import os
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

REQUIRED_SCOPE = "reportapa:reports:create"


def verify_mcp_access_token(token: str) -> dict:
    """Verify issuer, audience, signature, expiry and required scope.

    The configured identity provider must enforce token revocation, or issue
    short-lived access tokens. No unsigned tokens or symmetric JWTs are accepted.
    """
    issuer = os.getenv("REPORTAPA_OAUTH_ISSUER", "").rstrip("/")
    audience = os.getenv("REPORTAPA_OAUTH_AUDIENCE", "")
    jwks_url = os.getenv("REPORTAPA_OAUTH_JWKS_URL", "")
    if not issuer or not audience or not jwks_url:
        raise RuntimeError("OAuth no configurado")
    for url in (issuer, jwks_url):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.query):
            raise RuntimeError("Configuración OAuth insegura")
    if not token or len(token) > 8192:
        raise InvalidTokenError("Token ausente o demasiado largo")
    header = jwt.get_unverified_header(token)
    if header.get("alg") not in ("RS256", "ES256"):
        raise InvalidTokenError("Algoritmo no permitido")
    key = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300).get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token, key, algorithms=["RS256", "ES256"], issuer=issuer,
        audience=audience, options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        leeway=30,
    )
    scopes = claims.get("scope", "")
    if not isinstance(scopes, str) or REQUIRED_SCOPE not in scopes.split():
        raise InvalidTokenError("Permiso insuficiente")
    allowed_subject = os.getenv("REPORTAPA_OAUTH_ALLOWED_SUB", "").strip()
    if not allowed_subject:
        raise RuntimeError("Cuenta autorizada MCP no configurada")
    if claims["sub"] != allowed_subject:
        raise InvalidTokenError("Cuenta no autorizada para registrar reportes")
    return claims
