import uuid
from app import main as m

def test_aid_requires_auth():
    from fastapi.testclient import TestClient
    client = TestClient(m.app)
    assert client.get('/api/aid/session').status_code == 401
    assert client.post('/api/aid/deliveries', json={}).status_code == 401
    assert client.get('/api/admin/aid/workers').status_code == 401
    assert client.get('/api/admin/aid/deliveries').status_code == 401

def test_aid_page_and_citizen_form():
    from fastapi.testclient import TestClient
    client = TestClient(m.app)
    assert client.get('/entrega-ayuda').status_code == 200
    home = client.get('/').text
    assert 'Reportar daños' in home
    assert 'Entrega de ayuda' in home
    assert 'name="maps"' in home

def test_aid_flow(live, monkeypatch):
    admin_login = live.post('/api/admin/login', json={
        'username': 'Ayudapanama', 'password': 'test-password-123456'})
    assert admin_login.status_code == 200
    csrf = {'x-csrf-token': admin_login.json()['csrf']}
    name = 'Responsable ' + uuid.uuid4().hex[:10]
    created = live.post('/api/admin/aid/workers',
                        json={'full_name': name}, headers=csrf)
    assert created.status_code == 200, created.text
    worker_id, code = created.json()['id'], created.json()['code']
    assert len(code) == 6 and code.isdigit()
    with m.db() as c:
        original = c.execute('SELECT * FROM aid_workers WHERE id=%s', (worker_id,)).fetchone()
    assert any(w['id'] == worker_id for w in live.get('/api/admin/aid/workers').json()['workers'])
    assert live.post('/api/aid/login',
                     json={'full_name': name, 'code': 'incorrecto'}).status_code == 401
    login = live.post('/api/aid/login', json={'full_name': name, 'code': code})
    assert login.status_code == 200, login.text
    worker_csrf = {'x-csrf-token': login.json()['csrf']}
    payload = dict(beneficiary_name='Familia Prueba', beneficiary_id='8-888-888',
                   place='Santiago', aid_type='Agua potable',
                   idempotency_key=str(uuid.uuid4()))
    assert live.post('/api/aid/deliveries', json=payload).status_code == 403
    first = live.post('/api/aid/deliveries', json=payload, headers=worker_csrf)
    assert first.status_code == 200, first.text
    again = live.post('/api/aid/deliveries', json=payload, headers=worker_csrf)
    assert again.status_code == 200
    assert again.json()['id'] == first.json()['id']
    assert live.post('/api/aid/deliveries',
                     json={**payload, 'aid_type': 'Ropa'},
                     headers=worker_csrf).status_code == 409
    records = live.get('/api/admin/aid/deliveries')
    assert records.status_code == 200
    assert sum(d['id'] == first.json()['id'] for d in records.json()['deliveries']) == 1
    revoked = live.post('/api/admin/aid/workers/' + worker_id + '/revoke',
                        headers=csrf)
    assert revoked.status_code == 200
    assert live.get('/api/aid/session').status_code == 401

    assert not any(w['id'] == worker_id for w in live.get('/api/admin/aid/workers').json()['workers'])
    assert live.post('/api/aid/login', json={'full_name': name, 'code': code}).status_code == 401
    assert live.post('/api/admin/aid/workers/' + worker_id + '/reset-code', headers=csrf).status_code == 404
    # Force the generator to propose the retired code first: it must reject it.
    second_number = (int(code) + 1) % 1000000
    third_number = (int(code) + 2) % 1000000
    candidates = iter([int(code), second_number])
    monkeypatch.setattr('app.aid_delivery.secrets.randbelow', lambda _: next(candidates))
    recreated = live.post('/api/admin/aid/workers', json={'full_name': name}, headers=csrf)
    assert recreated.status_code == 200, recreated.text
    second_id, second_code = recreated.json()['id'], recreated.json()['code']
    assert second_id != worker_id and second_code != code
    candidates = iter([third_number])
    duplicate = live.post('/api/admin/aid/workers', json={'full_name': name}, headers=csrf)
    # The active-name constraint still forbids duplicate active credentials.
    assert duplicate.status_code == 409
    workers = live.get('/api/admin/aid/workers').json()['workers']
    assert [w['id'] for w in workers if w['full_name'] == name] == [second_id]
    with m.db() as c:
        history = c.execute('SELECT * FROM aid_workers WHERE id=%s', (worker_id,)).fetchone()
        assert history['active'] is False and history['revoked_at'] is not None
        for key in ('id', 'full_name', 'login_name', 'secret_hash', 'created_at'):
            assert history[key] == original[key]
        assert c.execute('SELECT worker_id FROM aid_deliveries WHERE id=%s', (first.json()['id'],)).fetchone()['worker_id'] == history['id']
    assert any(d['id'] == first.json()['id'] for d in live.get('/api/admin/aid/deliveries').json()['deliveries'])
    assert live.post('/api/aid/login', json={'full_name': name, 'code': code}).status_code == 401
    assert live.post('/api/aid/login', json={'full_name': name, 'code': second_code}).status_code == 200
    # Resetting the replacement must also skip both current and retired codes.
    candidates = iter([int(code), second_number, third_number])
    reset = live.post('/api/admin/aid/workers/' + second_id + '/reset-code', headers=csrf)
    assert reset.status_code == 200, reset.text
    third_code = reset.json()['code']
    assert third_code not in (code, second_code)
    assert live.get('/api/aid/session').status_code == 401
    assert live.post('/api/aid/login', json={'full_name': name, 'code': second_code}).status_code == 401
    assert live.post('/api/aid/login', json={'full_name': name, 'code': third_code}).status_code == 200
