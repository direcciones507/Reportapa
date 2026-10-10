import os, io, uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PIL import Image
from app import main as m
from psycopg.conninfo import conninfo_to_dict

@pytest.fixture
def data():
    return dict(name='Responsable Prueba',family_name='Familia Prueba',total_people='4',phone='+507 6123-4567',province='Veraguas',district='Santiago',township='Santiago',community='Sector prueba',maps='https://maps.app.goo.gl/abc123',damage='Daño de prueba',needs=['Agua potable'])

def test_validation(data):
    assert m.validate(data)['phone']=='61234567'
    for link in ['https://google.com.evil.test/maps','http://maps.app.goo.gl/a','https://google.com/search','https://user@google.com/maps','https://goo.gl/anything']:
        with pytest.raises(HTTPException): m.validate({**data,'maps':link})
    with pytest.raises(HTTPException): m.validate({**data,'damage':''})

def test_images():
    out=io.BytesIO();Image.new('RGB',(20,20)).save(out,'PNG');result=m.clean_photo(out.getvalue())
    assert Image.open(io.BytesIO(result)).format=='JPEG'
    with pytest.raises(HTTPException): m.clean_photo(b'fake image')
    with pytest.raises(HTTPException): m.clean_photo(b'x'*(5*1024*1024+1))

def test_excel(data):
    data=m.validate(data);data['name']='=HYPERLINK("evil")';data['damage']='secret damage';data['needs_detail']='private detail'
    rows=[dict(id='RPA-00000001',created_at=datetime.now(timezone.utc),data=data,status='pendiente')]
    wb=load_workbook(io.BytesIO(m.workbook(rows,'todos')))
    assert wb['Reportes']['C2'].data_type=='s'
    assert wb['Información']['B3'].value==1
    anonymous=load_workbook(io.BytesIO(m.workbook(rows,'todos',True)))
    text=str(list(anonymous['Reportes'].values))
    for private in ['HYPERLINK','61234567','abc123','secret damage','private detail','Sector prueba']: assert private not in text

def test_closed_and_auth(monkeypatch):
    monkeypatch.setenv('SESSION_SECRET','s'*40)
    monkeypatch.delenv('PUBLIC_REPORTS_ENABLED',raising=False)
    client=TestClient(m.app)
    assert client.post('/api/reports').status_code==503
    assert client.post('/api/admin/login',content=b'x'*4097).status_code==413
    for path in ['/api/admin/reports','/api/admin/export/master','/api/admin/export/area','/api/admin/export/anonymous','/api/admin/export/summary','/api/admin/reports/RPA-1/photos/file.jpg']:
        assert client.get(path).status_code==401
    assert client.get('/').status_code==200
    assert client.get('/').headers['cache-control']=='no-store'

@pytest.fixture
def live(monkeypatch,tmp_path):
    if not os.getenv('DATABASE_URL'): pytest.skip('PostgreSQL required')
    params=conninfo_to_dict(os.environ['DATABASE_URL'])
    if params.get('host') not in ('localhost','127.0.0.1') or params.get('dbname')!='reportapa_test':
        pytest.fail('Integration tests require disposable localhost database reportapa_test; no tables were changed')
    monkeypatch.setenv('SESSION_SECRET','test-secret-'*4)
    monkeypatch.setenv('ADMIN_PASSWORD','test-password-123456')
    monkeypatch.setenv('PHOTO_DIR',str(tmp_path))
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('PUBLIC_REPORTS_ENABLED','true')
    with TestClient(m.app) as client:
        with m.db() as c: c.execute('TRUNCATE reports,request_limits,admin_sessions,photo_cleanup,deleted_reports')
        yield client

def submit(client,data,key=None,extra=None,photos=None):
    fields={**data,'consent':'yes','idempotency_key':key or str(uuid.uuid4()),**(extra or {})}
    fields.pop('needs');fields['needs']='Agua potable'
    return client.post('/api/reports',data=fields,files=photos or {'photos':('',b'','application/octet-stream')})

def test_postgres_flow(live,data):
    key=str(uuid.uuid4());r=submit(live,data,key);assert r.status_code==200,r.text;identifier=r.json()['id'];assert identifier.startswith('RPA-')
    assert submit(live,data,key).json()['id']==identifier
    assert submit(live,{**data,'damage':'changed'},key).status_code==409
    dup=submit(live,{**data,'damage':'Posibles daños nuevos'});assert dup.status_code==409 and 'id' not in dup.json()
    assert submit(live,{**data,'damage':'Daños nuevos en el techo'},extra={'new_damage':'yes'}).status_code==200
    login=live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'});assert login.status_code==200
    csrf={'x-csrf-token':login.json()['csrf']}
    assert live.get('/api/admin/reports').json()['total']==2
    assert live.get('/api/admin/reports?province=Coclé').json()['total']==0
    assert live.patch('/api/admin/reports/'+identifier,json={'status':'visitado'}).status_code==403
    assert live.patch('/api/admin/reports/'+identifier,json={'status':'visitado'},headers=csrf).status_code==200
    assert live.get('/api/admin/reports?status=visitado&need=Agua%20potable').json()['total']==1
    r=live.get('/api/admin/export/master');assert r.status_code==200
    wb=load_workbook(io.BytesIO(r.content));assert wb['Reportes'].max_row==3
    assert live.get('/api/admin/export/summary').content.startswith(b'%PDF')
    assert live.post('/api/admin/logout',headers=csrf).status_code==200
    assert live.get('/api/admin/reports').status_code==401

def test_private_photos(live,data):
    out=io.BytesIO();Image.new('RGB',(20,20)).save(out,'PNG')
    r=submit(live,data,photos={'photos':('test.png',out.getvalue(),'image/png')});assert r.status_code==200,r.text
    live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    report=live.get('/api/admin/reports').json()['reports'][0];url='/api/admin/reports/'+report['id']+'/photos/'+report['photos'][0]
    assert live.get(url).status_code==200
    assert TestClient(m.app).get(url).status_code==401
    assert live.get('/static/'+report['photos'][0]).status_code==404

def test_rate_limit(live):
    for _ in range(10): assert live.post('/api/admin/login',json={'username':'Ayudapanama','password':'wrong'}).status_code==401
    assert live.post('/api/admin/login',json={'username':'Ayudapanama','password':'wrong'}).status_code==429

from pypdf import PdfReader

def test_help_excel_privacy(data):
    report=dict(id='RPA-00000001',created_at=datetime.now(timezone.utc),data=m.validate(data),status='visitado',estado_ayuda='parcial',ayuda_actualizada_at=datetime.now(timezone.utc),ayuda_observacion='=CONFIDENTIAL_NOTE')
    wb=load_workbook(io.BytesIO(m.workbook([report],'todos')))
    values=list(wb['Reportes'].values);assert values[1][-3]=='Ayuda parcial';assert values[1][-1]=='=CONFIDENTIAL_NOTE';assert wb['Reportes'].cell(2,len(values[0])).data_type=='s'
    anon=load_workbook(io.BytesIO(m.workbook([report],'todos',True)))
    text=str(list(anon['Reportes'].values));assert 'CONFIDENTIAL_NOTE' not in text;assert 'Ayuda parcial' in text;assert '61234567' not in text

def test_single_page_pdf(data,tmp_path):
    photos=[]
    for i,size in enumerate([(150,100),(100,150),(150,150)]):
        name=f'{i:032x}.jpg';Image.new('RGB',size,(50+i*40,120,180)).save(tmp_path/name);photos.append(name)
    d=m.validate(data);d['damage']='Daños en paredes. '*80;d['needs_detail']='Artículos y cantidades. '*60
    report=dict(id='RPA-00000001',created_at=datetime.now(timezone.utc),data=d,status='contactado',estado_ayuda='sin_ayuda',ayuda_actualizada_at=datetime.now(timezone.utc),ayuda_observacion='Observación privada. '*20,photos=photos)
    pdf=PdfReader(io.BytesIO(m.individual_pdf(report,tmp_path,m.HELP_STATES)))
    assert len(pdf.pages)==1
    text=pdf.pages[0].extract_text();assert 'Sin ayuda recibida' in text;assert 'Último seguimiento' in text;assert 'Ficha individual' in text
    assert len(pdf.pages[0].images)==3
    report['photos']=[];assert len(PdfReader(io.BytesIO(m.individual_pdf(report,tmp_path,m.HELP_STATES))).pages)==1

def test_help_persistence(live,data):
    id=submit(live,data).json()['id'];url='/api/admin/reports/'+id
    # New private routes cannot be accessed without a session.
    assert live.get(url+'/pdf').status_code==401
    login=live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'});csrf={'x-csrf-token':login.json()['csrf']}
    initial=live.get('/api/admin/reports').json()['reports'][0]
    assert initial['estado_ayuda']=='pendiente_confirmar' and initial['ayuda_actualizada_at'] is None
    assert live.patch(url,json={'estado_ayuda':'sin_ayuda'}).status_code==403
    for payload in [{'estado_ayuda':'received'},{'estado_ayuda':[]},{'estado_ayuda':'parcial','observacion':'x'*501},{'estado_ayuda':'parcial','observacion':42},{'observacion':'note'}]:
        assert live.patch(url,json=payload,headers=csrf).status_code==422
    assert live.patch(url,json={'estado_ayuda':'sin_ayuda','observacion':'Seguimiento privado'},headers=csrf).status_code==200
    # A fresh client/session reads the same persisted state.
    reader=TestClient(m.app);reader.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    report=reader.get('/api/admin/reports').json()['reports'][0]
    assert report['status']=='pendiente' and report['estado_ayuda']=='sin_ayuda'
    assert report['ayuda_actualizada_at'] and report['ayuda_observacion']=='Seguimiento privado';assert report['ayuda_admin']=='Ayudapanama'
    assert len(report['ayuda_historial'])==1 and report['ayuda_historial'][0]['anterior']=='pendiente_confirmar'
    assert report['ayuda_historial'][0]['administrador']=='Ayudapanama'
    assert live.patch(url,json={'estado_ayuda':'sin_ayuda','observacion':'Seguimiento privado'},headers=csrf).status_code==200
    same=live.get('/api/admin/reports').json()['reports'][0];assert len(same['ayuda_historial'])==1 and same['ayuda_actualizada_at']==report['ayuda_actualizada_at']
    assert live.patch(url,json={'status':'visitado'},headers=csrf).status_code==200
    assert live.get('/api/admin/reports?estado_ayuda=sin_ayuda&province=Veraguas&status=visitado').json()['total']==1
    assert live.get('/api/admin/reports?estado_ayuda=completa').json()['total']==0
    assert live.get('/api/admin/reports?estado_ayuda=wrong').status_code==422
    for kind in ['master','area','anonymous']:
        result=live.get('/api/admin/export/'+kind+'?estado_ayuda=sin_ayuda')
        assert result.status_code==200
        workbook=load_workbook(io.BytesIO(result.content));assert 'Sin ayuda recibida' in str(list(workbook['Reportes'].values))
        if kind=='anonymous': assert 'Seguimiento privado' not in str(list(workbook['Reportes'].values))
    pdf=live.get(url+'/pdf');assert pdf.status_code==200 and len(PdfReader(io.BytesIO(pdf.content)).pages)==1
    assert 'Sin ayuda recibida' in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert live.get('/api/admin/export/summary').content.startswith(b'%PDF')
    assert live.patch(url,json={'estado_ayuda':'completa','observacion':''},headers=csrf).status_code==200
    final=live.get('/api/admin/reports').json()['reports'][0];assert final['status']=='visitado';assert len(final['ayuda_historial'])==2
    # Re-running migrations preserves report data and follow-up history.
    with m.db() as c:
        c.execute((m.ROOT.parent/'migrations/002_help_followup.sql').read_text())
        persisted=c.execute('SELECT * FROM reports WHERE id=%s',(id,)).fetchone()
    assert persisted['estado_ayuda']=='completa' and len(persisted['ayuda_historial'])==2

def test_existing_reports_migration(live,data):
    with m.db() as c:
        c.execute('CREATE SCHEMA legacy_migration_test')
        c.execute('SET LOCAL search_path TO legacy_migration_test')
        c.execute((m.ROOT.parent/'migrations/001_initial.sql').read_text())
        r=c.execute('INSERT INTO reports(idempotency_key,request_hash,fingerprint,data) VALUES (%s,%s,%s,%s::jsonb) RETURNING id',(str(uuid.uuid4()),'old','old',__import__('json').dumps(m.validate(data)))).fetchone()
        c.execute((m.ROOT.parent/'migrations/002_help_followup.sql').read_text())
        c.execute((m.ROOT.parent/'migrations/002_help_followup.sql').read_text())
        old=c.execute('SELECT * FROM reports WHERE id=%s',(r['id'],)).fetchone()
        assert old['estado_ayuda']=='pendiente_confirmar';assert old['ayuda_historial']==[];assert old['status']=='pendiente';assert old['ayuda_actualizada_at'] is None
        assert old['data']['name']==data['name']
        with pytest.raises(__import__('psycopg').errors.CheckViolation):
            with c.transaction(): c.execute("UPDATE reports SET estado_ayuda='invalid'")
        c.execute('SET LOCAL search_path TO public')
        c.execute('DROP SCHEMA legacy_migration_test CASCADE')

PRIVATE_GETS=['/api/admin/session','/api/admin/reports','/api/admin/export/master','/api/admin/export/area','/api/admin/export/anonymous','/api/admin/export/summary','/api/admin/reports/RPA-00000001/photos/00000000000000000000000000000000.jpg','/api/admin/reports/RPA-00000001/pdf']

def test_owner_login_logout_and_route_protection(live):
    for body in [{'password':'test-password-123456'},{'username':'otro','password':'test-password-123456'},{'username':'Ayudapanama','password':'incorrecta'},{'username':'Ayudapanama','password':'contraseña inválida'}]:
        assert live.post('/api/admin/login',json=body).status_code==401
    for path in PRIVATE_GETS: assert live.get(path).status_code==401
    assert live.patch('/api/admin/reports/RPA-00000001',json={'estado_ayuda':'parcial'}).status_code==401
    result=live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    assert result.status_code==200
    cookie=result.headers['set-cookie'];assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age=3600' in cookie
    token=live.cookies.get('rpa_session');csrf={'x-csrf-token':result.json()['csrf']}
    assert live.get('/api/admin/session').json()['username']=='Ayudapanama'
    assert live.post('/api/admin/logout').status_code==403
    with m.db() as c:
        session=c.execute('SELECT * FROM admin_sessions').fetchone()
        assert session['username']=='Ayudapanama' and session['token_hash']!=token
    assert live.post('/api/admin/logout',headers=csrf).status_code==200
    replay=TestClient(m.app);replay.cookies.set('rpa_session',token)
    for path in PRIVATE_GETS: assert replay.get(path).status_code==401
    assert replay.patch('/api/admin/reports/RPA-00000001',json={'status':'visitado'},headers=csrf).status_code==401

def test_session_expiration_tampering_and_password_rotation(live,monkeypatch):
    response=live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'});token=live.cookies.get('rpa_session')
    client=TestClient(m.app);client.cookies.set('rpa_session',token[:-1]+('a' if token[-1]!='a' else 'b'))
    assert client.get('/api/admin/session').status_code==401
    monkeypatch.setenv('ADMIN_PASSWORD','a-new-private-password-123')
    assert live.get('/api/admin/session').status_code==401
    monkeypatch.setenv('ADMIN_PASSWORD','test-password-123456')
    with m.db() as c: c.execute("UPDATE admin_sessions SET expires_at=now()-interval '1 second'")
    assert live.get('/api/admin/session').status_code==401
    # Legacy signed tokens without a server session no longer grant access.
    value=str(int(__import__('time').time()+3600))+'.'+'f'*48
    client.cookies.set('rpa_session',value+'.'+m.signing(value))
    assert client.get('/api/admin/session').status_code==401

def test_secure_cookie(live,monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE','true')
    response=live.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    assert response.status_code==200 and 'Secure' in response.headers['set-cookie']

def test_production_configuration_guard(monkeypatch,tmp_path):
    monkeypatch.setenv('SESSION_SECRET','s'*40);monkeypatch.setenv('ADMIN_PASSWORD','a'*20)
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID','test-only');monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH',raising=False)
    with pytest.raises(RuntimeError,match='volumen'): m.validate_runtime()
    monkeypatch.setenv('RAILWAY_VOLUME_MOUNT_PATH',str(tmp_path));monkeypatch.setenv('PHOTO_DIR',str(tmp_path/'photos'));monkeypatch.setenv('COOKIE_SECURE','true')
    m.validate_runtime()
    monkeypatch.setenv('PHOTO_DIR','/tmp/outside-photo-volume')
    with pytest.raises(RuntimeError,match='volumen'): m.validate_runtime()
    monkeypatch.setenv('PHOTO_DIR',str(tmp_path/'photos'));monkeypatch.setenv('COOKIE_SECURE','false')
    with pytest.raises(RuntimeError,match='HTTPS'): m.validate_runtime()
