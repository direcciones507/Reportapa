import errno,io,json,uuid
from collections import namedtuple
from contextlib import contextmanager
import pytest,psycopg
from PIL import Image
from fastapi.testclient import TestClient
from test_app import live,data,submit
from app import main as m


def photo():
    image=io.BytesIO();Image.new('RGB',(40,40)).save(image,'PNG')
    return {'photos':('synthetic.png',image.getvalue(),'image/png')}


def login(client):
    response=client.post('/api/admin/login',json={'username':m.ADMIN_USERNAME,'password':'test-password-123456'})
    assert response.status_code==200,response.text


@pytest.mark.parametrize('failure',['full','reserve','write','unavailable'])
def test_photo_failure_confirms_family_and_retries_same_id(live,data,monkeypatch,failure,caplog):
    key=str(uuid.uuid4());original=m.os.open
    def fail(*args,**kwargs):raise OSError(errno.ENOSPC if failure=='full' else errno.EIO,'synthetic private storage failure')
    with monkeypatch.context() as patch:
        if failure=='full':patch.setattr(m.os,'fsync',fail)
        elif failure=='reserve':patch.setattr(m.shutil,'disk_usage',lambda _:namedtuple('disk','total used free')(100,100,0))
        elif failure=='unavailable':patch.setattr(m,'photo_dir',fail)
        else:
            def failed_open(path,*args,**kwargs):
                if str(path).endswith('.jpg'):return fail()
                return original(path,*args,**kwargs)
            patch.setattr(m.os,'open',failed_open)
        response=submit(live,data,key,photos=photo())
    assert response.status_code==200,response.text
    assert response.json()['photo_warning']==m.PHOTO_WARNING
    assert 'photo_storage_unavailable' in caplog.text
    with m.db() as c:
        record=c.execute('SELECT * FROM reports').fetchone()
        assert record['id']==response.json()['id'] and record['photos']==[] and record['data']==m.validate(data)
        assert record['photo_upload_failed']
    for attachments in (photo(),None):
        retry=submit(live,data,key,photos=attachments)
        assert retry.status_code==200 and retry.json()['id']==record['id']
        assert retry.json()['photo_warning']==m.PHOTO_WARNING
    assert submit(live,{**data,'damage':'Changed family information'},key).status_code==409
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==1
    assert not list(m.photo_dir().glob('*.jpg'))


def test_without_photo_does_not_depend_on_photo_volume(live,data,monkeypatch):
    def unavailable():raise PermissionError('synthetic private storage unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(m,'photo_dir',unavailable)
        response=submit(live,data)
    assert response.status_code==200 and 'photo_warning' not in response.json()
    with m.db() as c:assert c.execute('SELECT photos FROM reports').fetchone()['photos']==[]


def test_only_one_new_photo_but_historical_three_remain_private(live,data):
    attachments=[('photos',value) for value in photo().values()]*2
    assert submit(live,data,photos=attachments).status_code in (400,422)
    response=submit(live,data,photos=photo());assert response.status_code==200
    identifier=response.json()['id'];names=[uuid.uuid4().hex+'.jpg' for _ in range(3)]
    payload=m.clean_photo(photo()['photos'][1])
    for name in names:(m.photo_dir()/name).write_bytes(payload)
    # A historical fixture, not a new citizen upload; no production data involved.
    with m.db() as c:c.execute('UPDATE reports SET photos=%s::jsonb WHERE id=%s',(json.dumps(names),identifier))
    assert live.get('/api/admin/storage').status_code==401
    login(live)
    assert live.get('/api/admin/reports').json()['reports'][0]['photos']==names
    for name in names:assert live.get(f'/api/admin/reports/{identifier}/photos/{name}').content==payload
    assert live.get(f'/api/admin/reports/{identifier}/pdf').status_code==200
    assert live.get('/api/admin/storage').json()['photographs']==4 # Includes the first stored file.


@pytest.mark.parametrize('percent,alert',[(69,None),(70,70),(84,70),(85,85),(94,85),(95,95),(100,95)])
def test_real_storage_indicators_and_thresholds(live,data,monkeypatch,percent,alert):
    submit(live,data);login(live)
    disk=namedtuple('disk','total used free')(10000,percent*100,10000-percent*100)
    monkeypatch.setattr(m.shutil,'disk_usage',lambda _:disk)
    result=live.get('/api/admin/storage').json()
    assert result['total_reports']==1 and result['photographs']==0
    assert result['used_bytes']==disk.used and result['available_bytes']==disk.free
    assert result['occupation_percent']==percent and result['alert']==alert


def test_unavailable_indicators_do_not_invent_space_or_photo_counts(live,data,monkeypatch):
    submit(live,data);login(live)
    def unavailable(_):raise PermissionError('synthetic mount failure')
    monkeypatch.setattr(m.shutil,'disk_usage',unavailable)
    result=live.get('/api/admin/storage').json()
    assert result['total_reports']==1 and not result['storage_available']
    assert all(result[field] is None for field in ('photographs','used_bytes','available_bytes','occupation_percent'))


def test_photo_failure_with_lost_commit_acknowledgement(live,data,monkeypatch):
    original=m.db;calls=0
    @contextmanager
    def interrupted():
        nonlocal calls
        calls+=1;current=calls
        with original() as c:yield c
        if current==2:raise psycopg.OperationalError('synthetic lost COMMIT acknowledgement')
    def full(_):raise OSError(errno.ENOSPC,'synthetic full volume')
    with monkeypatch.context() as patch:
        patch.setattr(m,'db',interrupted);patch.setattr(m.os,'fsync',full)
        response=submit(live,data,photos=photo())
    assert response.status_code==200 and response.json()['photo_warning']==m.PHOTO_WARNING
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==1


def test_startup_survives_photo_directory_outage(live,data,monkeypatch):
    def unavailable():raise OSError(errno.EIO,'synthetic unavailable volume')
    monkeypatch.setattr(m,'photo_dir',unavailable)
    with TestClient(m.app) as restarted:
        assert submit(restarted,data).status_code==200


def test_thirty_thousand_records_have_no_accumulated_limit(live,data):
    payload=json.dumps(m.validate(data))
    with m.db() as c:
        c.execute("INSERT INTO reports(idempotency_key,request_hash,fingerprint,data,dedup_keys) SELECT md5('capacity-'||n)::uuid,md5('hash-'||n),md5('fingerprint-'||n),%s::jsonb,ARRAY['synthetic-'||n] FROM generate_series(1,30000) n",(payload,))
    response=submit(live,{**data,'phone':'69999999','family_name':'Familia adicional','maps':'https://maps.app.goo.gl/additional'})
    assert response.status_code==200,response.text
    login(live)
    page=live.get('/api/admin/reports?page=1501').json()
    assert page['total']==30001 and len(page['reports'])==1
    assert live.get('/api/admin/storage').json()['total_reports']==30001
    # Separate transaction confirms persistence, sequence growth and no ID truncation.
    with m.db() as c:
        assert c.execute('SELECT count(DISTINCT id) AS n FROM reports').fetchone()['n']==30001
        assert c.execute('SELECT report_number_label(100000000) AS id').fetchone()['id']=='RPA-100000000'


def test_failed_new_photo_preserves_existing_photo(live,data,monkeypatch):
    first=submit(live,data,photos=photo()).json()['id']
    with m.db() as c:name=c.execute('SELECT photos FROM reports WHERE id=%s',(first,)).fetchone()['photos'][0]
    path=m.photo_dir()/name;before=path.read_bytes()
    def full(_):raise OSError(errno.ENOSPC,'synthetic volume full')
    with monkeypatch.context() as patch:
        patch.setattr(m.os,'fsync',full)
        second=submit(live,{**data,'phone':'68888888','family_name':'Otra familia','maps':'https://maps.app.goo.gl/other'},photos=photo())
    assert second.status_code==200 and second.json()['id']!=first
    assert path.read_bytes()==before
    with m.db() as c:assert c.execute('SELECT photos FROM reports WHERE id=%s',(first,)).fetchone()['photos']==[name]


def test_photo_fallback_never_confirms_failed_database_commit(live,data,monkeypatch):
    original=m.db;calls=0;key=str(uuid.uuid4())
    @contextmanager
    def failed_commit():
        nonlocal calls
        calls+=1;current=calls
        with original() as c:
            yield c
            if current==2:raise psycopg.OperationalError('synthetic transaction rollback')
    def full(_):raise OSError(errno.ENOSPC,'synthetic volume full')
    with monkeypatch.context() as patch:
        patch.setattr(m,'db',failed_commit);patch.setattr(m.os,'fsync',full)
        response=submit(live,data,key,photos=photo())
    assert response.status_code==503 and 'id' not in response.json()
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==0
    retry=submit(live,data,key);assert retry.status_code==200
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==1


def test_cleanup_queue_outage_cannot_cancel_confirmed_family(live,data,monkeypatch,caplog):
    from pathlib import Path
    original=m.db;unlink=Path.unlink;calls=0
    @contextmanager
    def cleanup_outage():
        nonlocal calls
        calls+=1
        if calls==3:raise psycopg.errors.QueryCanceled('synthetic cleanup queue unavailable')
        with original() as c:yield c
    def full(_):raise OSError(errno.ENOSPC,'synthetic volume full')
    def denied(path,*args,**kwargs):
        if path.suffix=='.jpg':raise PermissionError('synthetic partial photo removal failure')
        return unlink(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(m,'db',cleanup_outage);patch.setattr(m.os,'fsync',full);patch.setattr(Path,'unlink',denied)
        response=submit(live,data,photos=photo())
    assert response.status_code==200 and response.json()['photo_warning']==m.PHOTO_WARNING
    assert 'photo_cleanup_queue_unavailable' in caplog.text
    with m.db() as c:
        row=c.execute('SELECT id,photos FROM reports').fetchone()
        assert row['id']==response.json()['id'] and row['photos']==[]
