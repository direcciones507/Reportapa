"""MCP tool contract for ReportaPA.

This module describes the single authorized write operation. It is deliberately
not exposed as an unauthenticated HTTP endpoint. The MCP transport and OAuth
resource-server validation must be completed before mounting it.
"""

REGISTER_REPORT_TOOL = {
    "name": "registrar_reporte",
    "description": (
        "Registra un reporte de daños autorizado en ReportaPA y devuelve "
        "el número oficial. Requiere consentimiento explícito y confirmación "
        "del usuario antes de escribir. Nunca invente números de reporte."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "idempotency_key", "consent", "name", "phone", "province",
            "district", "township", "community", "damage", "needs",
        ],
        "properties": {
            "idempotency_key": {"type": "string", "format": "uuid"},
            "consent": {"type": "string", "enum": ["yes"]},
            "name": {"type": "string", "minLength": 1},
            "phone": {"type": "string", "minLength": 7},
            "province": {"type": "string", "minLength": 1},
            "district": {"type": "string", "minLength": 1},
            "township": {"type": "string", "minLength": 1},
            "community": {"type": "string", "minLength": 1},
            "maps": {"type": "string"},
            "damage_type": {"type": "string"},
            "damage": {"type": "string", "minLength": 1},
            "needs": {"type": "array", "items": {"type": "string"}},
            "needs_detail": {"type": "string"},
            "reporting_for_self": {"type": "string", "enum": ["yes", "no"]},
            "reporter_name": {"type": "string"},
            "new_damage": {"type": "string", "enum": ["yes", "no"]},
        },
    },
}
