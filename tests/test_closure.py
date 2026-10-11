import io
import os
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from app import main as m
from app.photo_maintenance import cleanup_photos
from test_app import data, live, submit


def login(client):
    r=client.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    assert r.status_code==200
    return {'x-csrf-token':r.json()['csrf']}


def test_phone_invalid_text(data):
    for value in ['abc61234567','https://evil.test/61234567','61234567 ext']:
        with pytest.raises(HTTPException):m.validate({**data,'phone':value})
    assert m.validate({**data,'phone':'(+507) 6123-4567'})['phone']=='61234567'


def test_private_malformed_json_and_no_side_effect(live,data):
    identifier=submit(live,data).json()['id'];csrf=login(live)
    for method,path in [('POST','/api/admin/login'),('PATCH','/api/admin/reports/'+identifier),('DELETE','/api/admin/reports/'+identifier)]:
        for body in [b'{bad',b'\xff']:
            assert live.request(method,path,content=body,headers={**csrf,'content-type':'application/json'}).status_code==422
    assert live.get('/api/admin/reports').json()['total']==1
    assert live.get('/api/admin/reports').json()['reports'][0]['status']=='pendiente'


def test_missing_photo_is_private_not_server_error(live,data):
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'PNG')
    identifier=submit(live,data,photos={'photos':('test.png',image.getvalue(),'image/png')}).json()['id'];login(live)
    name=live.get('/api/admin/reports').json()['reports'][0]['photos'][0]
    path=m.photo_dir()/name
    assert path.stat().st_mode & 0o777 == 0o600
    path.unlink()
    url='/api/admin/reports/'+identifier+'/photos/'+name
    assert live.get(url).status_code==404
    assert TestClient(m.app).get(url).status_code==401
    assert live.get('/api/admin/reports/'+identifier+'/pdf').status_code==200


def test_failed_photo_write_uses_existing_cleanup_queue(live,data,monkeypatch):
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'PNG')
    original_fdopen=os.fdopen;original_unlink=Path.unlink
    class BrokenWriter:
        def __init__(self,descriptor):self.file=original_fdopen(descriptor,'wb')
        def __enter__(self):return self
        def write(self,content):
            self.file.write(content[:10]);raise OSError('discardable simulated full volume')
        def __exit__(self,*args):self.file.close()
    def denied(path,*args,**kwargs):
        if path.suffix=='.jpg':raise PermissionError('discardable simulated unlink failure')
        return original_unlink(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(os,'fdopen',lambda descriptor,mode:BrokenWriter(descriptor))
        patch.setattr(Path,'unlink',denied)
        response=submit(live,data,photos={'photos':('test.png',image.getvalue(),'image/png')})
        assert response.status_code==200 and response.json()['photo_warning']==m.PHOTO_WARNING
    with m.db() as c:
        assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==1
        assert c.execute('SELECT photos FROM reports').fetchone()['photos']==[]
        assert c.execute('SELECT count(*) AS n FROM photo_cleanup').fetchone()['n']==1
    cleanup_photos(m.db,m.photo_dir())
    assert not list(m.photo_dir().glob('*.jpg'))
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM photo_cleanup').fetchone()['n']==0


def test_integration_fixture_refuses_foreign_database(monkeypatch,tmp_path):
    from test_app import live as fixture
    monkeypatch.setenv('DATABASE_URL','postgresql://test-only@localhost/another_project')
    with pytest.raises(pytest.fail.Exception,match='no tables were changed'):
        next(fixture.__wrapped__(monkeypatch,tmp_path))


def test_invalid_cookie_configuration_refused(monkeypatch):
    monkeypatch.setenv('SESSION_SECRET','test-only-'*5)
    monkeypatch.setenv('ADMIN_PASSWORD','test-only-password-123')
    monkeypatch.setenv('COOKIE_SECURE','typo')
    with pytest.raises(RuntimeError,match='COOKIE_SECURE'):m.validate_runtime()
