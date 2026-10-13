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

def test_aid_flow(live):
    admin_login = live.post('/api/admin/login', json={
        'username': 'Ayudapanama', 'password': 'test-password-123456'})
    assert admin_login.status_code == 200
    csrf = {'x-csrf-token': admin_login.json()['csrf']}
    name = 'Responsable ' + uuid.uuid4().hex[:10]
    created = live.post('/api/admin/aid/workers',
                        json={'full_name': name}, headers=csrf)
    assert created.status_code == 200, created.text
    worker_id, code = created.json()['id'], created.json()['code']
    assert len(code) == 6 and code.isdecimal()
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
