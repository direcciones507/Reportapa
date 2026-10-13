"""Private aid-delivery API. Kept separate from existing citizen reports."""
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

def install(app, db, admin, limit, signing, json_payload):
    def code_hash(code, salt=None):
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', code.encode(), bytes.fromhex(salt), 260000).hex()
        return salt + ':' + digest

    def verify_code(code, stored):
        try:
            salt, expected = stored.split(':', 1)
            return hmac.compare_digest(code_hash(code, salt), stored)
        except (ValueError, TypeError):
            return False

    def worker(request: Request):
        token = request.cookies.get('rpa_aid_session', '')
        if len(token) != 64 or not re.fullmatch('[0-9a-f]{64}', token):
            raise HTTPException(401, 'Inicie sesión')
        with db() as c:
            found = c.execute("""SELECT w.id,w.full_name FROM aid_worker_sessions s
                JOIN aid_workers w ON w.id=s.worker_id
                WHERE s.token_hash=%s AND s.expires_at>now() AND w.active=true""",
                (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not found:
            raise HTTPException(401, 'Inicie sesión')
        if request.method != 'GET' and not hmac.compare_digest(
                request.headers.get('x-csrf-token', ''), signing(token)):
            raise HTTPException(403, 'Solicitud inválida')
        return found

    def field(payload, key, max_length):
        value = payload.get(key)
        if not isinstance(value, str) or not (3 <= len(value.strip()) <= max_length):
            raise HTTPException(422, 'Revise el campo: ' + key)
        return value.strip()

    @app.post('/api/aid/login')
    async def aid_login(request: Request):
        limit(request, 'aid-login', 10)
        payload = await json_payload(request)
        if not isinstance(payload, dict):
            raise HTTPException(401, 'Credenciales inválidas')
        name = payload.get('full_name', '')
        code = payload.get('code', '')
        if not isinstance(name, str) or not isinstance(code, str) or len(name) > 180 or len(code) > 128:
            raise HTTPException(401, 'Credenciales inválidas')
        login_name = ' '.join(name.casefold().split())
        limit(request, 'aid-account', 10, identity=login_name)
        with db() as c:
            record = c.execute('SELECT id,secret_hash FROM aid_workers WHERE login_name=%s AND active=true', (login_name,)).fetchone()
        if not record or not verify_code(code, record['secret_hash']):
            raise HTTPException(401, 'Credenciales inválidas')
        token = secrets.token_hex(32)
        with db() as c:
            c.execute("""INSERT INTO aid_worker_sessions(token_hash,worker_id,expires_at)
                VALUES (%s,%s,now()+interval '8 hours')""",
                (hashlib.sha256(token.encode()).hexdigest(), record['id']))
        response = JSONResponse({'ok': True, 'csrf': signing(token)})
        response.set_cookie('rpa_aid_session', token, httponly=True,
                            secure=os.getenv('COOKIE_SECURE', 'true') == 'true',
                            samesite='strict', max_age=28800, path='/api/aid')
        return response

    @app.get('/api/aid/session')
    def aid_session(person=Depends(worker)):
        return {'full_name': person['full_name']}

    @app.post('/api/aid/logout')
    def aid_logout(request: Request, person=Depends(worker)):
        token = request.cookies.get('rpa_aid_session', '')
        with db() as c:
            c.execute('DELETE FROM aid_worker_sessions WHERE token_hash=%s',
                      (hashlib.sha256(token.encode()).hexdigest(),))
        response = JSONResponse({'ok': True})
        response.delete_cookie('rpa_aid_session', path='/api/aid')
        return response

    @app.post('/api/aid/deliveries')
    async def create_delivery(request: Request, person=Depends(worker)):
        limit(request, 'aid-submit', 120, identity=str(person['id']))
        payload = await json_payload(request)
        if not isinstance(payload, dict):
            raise HTTPException(422, 'Solicitud inválida')
        values = [field(payload, key, max_length) for key, max_length in (
            ('beneficiary_name', 180), ('beneficiary_id', 50),
            ('place', 300), ('aid_type', 500))]
        try:
            key = uuid.UUID(str(payload.get('idempotency_key', '')))
        except ValueError:
            raise HTTPException(422, 'Clave de envío inválida')
        with db() as c:
            record = c.execute("""INSERT INTO aid_deliveries
                (id,worker_id,beneficiary_name,beneficiary_id,place,aid_type,idempotency_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(worker_id,idempotency_key) DO NOTHING RETURNING id,created_at""",
                (uuid.uuid4(), person['id'], *values, key)).fetchone()
            if record is None:
                record = c.execute("""SELECT id,created_at,beneficiary_name,beneficiary_id,place,aid_type
                    FROM aid_deliveries WHERE worker_id=%s AND idempotency_key=%s""",
                    (person['id'], key)).fetchone()
                if [record[k] for k in ('beneficiary_name','beneficiary_id','place','aid_type')] != values:
                    raise HTTPException(409, 'Clave utilizada con datos diferentes')
        return {'id': str(record['id']), 'created_at': record['created_at'].isoformat()}

    @app.get('/api/admin/aid/workers')
    def admin_workers(token=Depends(admin)):
        with db() as c:
            records = c.execute("""SELECT id,full_name,active,created_at,revoked_at
                FROM aid_workers ORDER BY created_at DESC""").fetchall()
        return {'workers': records}

    @app.post('/api/admin/aid/workers')
    async def add_worker(request: Request, token=Depends(admin)):
        payload = await json_payload(request)
        if not isinstance(payload, dict):
            raise HTTPException(422, 'Solicitud inválida')
        name = field(payload, 'full_name', 180)
        login_name = ' '.join(name.casefold().split())
        code = secrets.token_urlsafe(24)
        try:
            with db() as c:
                record = c.execute("""INSERT INTO aid_workers(id,full_name,login_name,secret_hash)
                    VALUES (%s,%s,%s,%s) RETURNING id""",
                    (uuid.uuid4(), name, login_name, code_hash(code))).fetchone()
        except Exception as exc:
            if getattr(exc, 'sqlstate', None) == '23505':
                raise HTTPException(409, 'Responsable ya registrado')
            raise
        return {'id': str(record['id']), 'full_name': name, 'code': code}

    @app.post('/api/admin/aid/workers/{worker_id}/revoke')
    def revoke_worker(worker_id: uuid.UUID, token=Depends(admin)):
        with db() as c:
            record = c.execute("""UPDATE aid_workers SET active=false,revoked_at=now()
                WHERE id=%s AND active=true RETURNING id""", (worker_id,)).fetchone()
            if not record:
                raise HTTPException(404, 'Responsable no encontrado o inactivo')
            c.execute('DELETE FROM aid_worker_sessions WHERE worker_id=%s', (worker_id,))
        return {'ok': True}

    @app.get('/api/admin/aid/deliveries')
    def admin_deliveries(token=Depends(admin)):
        with db() as c:
            records = c.execute("""SELECT d.id,d.beneficiary_name,d.beneficiary_id,
                d.place,d.aid_type,d.created_at,w.full_name AS worker_name
                FROM aid_deliveries d JOIN aid_workers w ON w.id=d.worker_id
                ORDER BY d.created_at DESC LIMIT 200""").fetchall()
        return {'deliveries': records}
