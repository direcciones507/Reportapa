"""Destructive recovery is allowed ONLY in the disposable CI database."""
import io
import json
import os
import shutil
import subprocess
import socket
import sys
import time
import httpx
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app import main as m
from test_app import live, data, submit


def login(client):
    response=client.post('/api/admin/login',json={'username':'Ayudapanama','password':'test-password-123456'})
    assert response.status_code==200
    return {'x-csrf-token':response.json()['csrf']}


def test_closed_preproduction_secure_session(live,monkeypatch):
    monkeypatch.setenv('PUBLIC_REPORTS_ENABLED','false')
    monkeypatch.setenv('COOKIE_SECURE','true')
    with TestClient(m.app,base_url='https://preproduction.test') as client:
        assert client.get('/health').status_code==200
        assert client.post('/api/reports').status_code==503
        assert client.get('/api/admin/reports').status_code==401
        response=client.post('/api/admin/login',json={'username':'Ayudapanama','password':'wrong'})
        assert response.status_code==401
        csrf=login(client)
        cookie=client.cookies.get('rpa_session')
        assert client.get('/api/admin/reports').status_code==200
        assert client.post('/api/admin/logout',headers=csrf).status_code==200
        client.cookies.set('rpa_session',cookie)
        assert client.get('/api/admin/reports').status_code==401
        assert client.post('/api/reports').status_code==503


def test_logical_backup_restore_isolated(live,data,tmp_path,monkeypatch):
    if os.getenv('REPORTAPA_RECOVERY_TEST')!='disposable-ci':
        pytest.skip('Explicit disposable CI recovery opt-in required')
    source=os.environ['DATABASE_URL'];params=conninfo_to_dict(source)
    assert params.get('host') in ('localhost','127.0.0.1') and params.get('dbname')=='reportapa_test'
    assert shutil.which('pg_dump') and shutil.which('pg_restore'), 'PostgreSQL client required in CI'
    image=io.BytesIO();Image.new('RGB',(20,20),(10,90,180)).save(image,'PNG')
    identifier=submit(live,data,photos={'photos':('discardable.png',image.getvalue(),'image/png')}).json()['id']
    csrf=login(live)
    assert live.patch('/api/admin/reports/'+identifier,json={'estado_ayuda':'parcial','observacion':'Solo prueba'},headers=csrf).status_code==200
    report=live.get('/api/admin/reports').json()['reports'][0]
    photos=m.photo_dir();snapshot=tmp_path/'snapshot';snapshot.mkdir(mode=0o700)
    shutil.copytree(photos,snapshot/'photos',ignore=shutil.ignore_patterns('snapshot'))
    dump=snapshot/'database.dump'
    # Credentials are in the subprocess environment, never command arguments or logs.
    env=os.environ.copy()
    env.update({'PGHOST':params['host'],'PGPORT':params.get('port','5432'),'PGUSER':params['user'],'PGPASSWORD':params.get('password',''),'PGDATABASE':params['dbname']})
    subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl','--file',str(dump)],env=env,check=True,capture_output=True)
    assert dump.stat().st_size>0
    assert live.request('DELETE','/api/admin/reports/'+identifier,json={'confirm':'ELIMINAR '+identifier},headers=csrf).status_code==200
    ledger=live.get('/api/admin/export/erasures').json()
    (snapshot/'erasures.json').write_text(json.dumps(ledger));dump.chmod(0o600)
    restored_name='reportapa_restore_'+uuid.uuid4().hex
    target=make_conninfo(source,dbname=restored_name)
    with psycopg.connect(source,autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(restored_name)))
    try:
        restore_env={**env,'PGDATABASE':restored_name}
        subprocess.run(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname',restored_name,str(dump)],env=restore_env,check=True,capture_output=True)
        restored_photos=tmp_path/'restored-photos';shutil.copytree(snapshot/'photos',restored_photos)
        monkeypatch.setenv('DATABASE_URL',target);monkeypatch.setenv('PHOTO_DIR',str(restored_photos));monkeypatch.setenv('PUBLIC_REPORTS_ENABLED','false')
        with m.db() as connection:connection.execute('DELETE FROM admin_sessions')
        # Two fresh application lifespans: migrations repeat and photos survive.
        for _ in range(2):
            with TestClient(m.app) as restored:
                restored_csrf=login(restored)
                assert restored.get('/health').status_code==200
                assert restored.post('/api/reports').status_code==503
                r=restored.get('/api/admin/reports').json()['reports'][0]
                assert r['id']==identifier and r['estado_ayuda']=='parcial' and r['ayuda_historial']
                photo_url='/api/admin/reports/'+identifier+'/photos/'+r['photos'][0]
                assert restored.get(photo_url).content==(snapshot/'photos'/r['photos'][0]).read_bytes()
                assert TestClient(m.app).get(photo_url).status_code==401
                assert restored.get('/api/admin/export/master').content.startswith(b'PK')
                assert restored.get('/api/admin/export/anonymous').content.startswith(b'PK')
                assert len(PdfReader(io.BytesIO(restored.get('/api/admin/reports/'+identifier+'/pdf').content)).pages)==1
        # Real process restarts bind only loopback; no public deployment.
        for _ in range(2):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=os.environ.copy(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=2) as running:
                    deadline=time.monotonic()+20
                    while True:
                        assert process.poll() is None, 'Preproduction process stopped during startup'
                        try:
                            if running.get('/health').status_code==200:break
                        except httpx.TransportError:pass
                        assert time.monotonic()<deadline, 'Preproduction process health timeout'
                        time.sleep(0.1)
                    assert running.post('/api/reports').status_code==503
                    login(running)
                    assert running.get(photo_url).content==(snapshot/'photos'/r['photos'][0]).read_bytes()
                    assert running.get('/api/admin/reports').json()['total']==1
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
        with TestClient(m.app) as restored:
            restored_csrf=login(restored)
            for entry in json.loads((snapshot/'erasures.json').read_text()):
                assert restored.request('DELETE','/api/admin/reports/'+entry['id'],json={'confirm':'ELIMINAR '+entry['id']},headers=restored_csrf).status_code==200
            assert restored.get('/api/admin/reports?archive=all').json()['total']==0
            assert not list(restored_photos.glob('*.jpg'))
            assert restored.post('/api/reports').status_code==503
    finally:
        monkeypatch.setenv('DATABASE_URL',source)
        with psycopg.connect(source,autocommit=True) as connection:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(restored_name)))


def test_secret_generation_private_and_no_overwrite(tmp_path,capsys):
    from scripts.generate_session_secret import generate
    destination=tmp_path/'session.env'
    generate(destination)
    value=destination.read_text()
    assert value.startswith('SESSION_SECRET=') and len(value.split('=',1)[1].strip())>=32
    assert destination.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):generate(destination)
    assert destination.read_text()==value
    assert capsys.readouterr().out==''
