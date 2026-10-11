import concurrent.futures,uuid
from test_app import live,data,submit
from app import main as m

def test_shared_connection_families(live,data):
    for i in range(25):
        response=submit(live,{**data,'phone':str(61000000+i),'family_name':f'Familia {i}','maps':f'https://maps.app.goo.gl/prueba{i}'})
        assert response.status_code==200,response.text
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==25

def test_identity_abuse_remains_limited(live,data):
    for i in range(20):
        response=submit(live,{**data,'damage':f'Daño {i}'},extra={'new_damage':'yes'})
        assert response.status_code==200,response.text
    assert submit(live,{**data,'damage':'Intento 21'},extra={'new_damage':'yes'}).status_code==429

def test_concurrent_idempotency(live,data):
    key=str(uuid.uuid4())
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        responses=list(executor.map(lambda _:submit(live,data,key),range(10)))
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['id'] for r in responses})==1
    with m.db() as c:assert c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']==1
    assert m.pool.get_stats()['pool_size']<=8

def test_lost_commit_acknowledgement_keeps_saved_photo(live,data,monkeypatch):
    import io,psycopg
    from contextlib import contextmanager
    from PIL import Image
    original=m.db;calls=0
    @contextmanager
    def interrupted():
        nonlocal calls
        calls+=1;current=calls
        with original() as connection:yield connection
        if current==2:raise psycopg.OperationalError('synthetic lost COMMIT acknowledgement')
    image=io.BytesIO();Image.new('RGB',(40,40)).save(image,'PNG')
    with monkeypatch.context() as patch:
        patch.setattr(m,'db',interrupted)
        response=submit(live,data,photos={'photos':('synthetic.png',image.getvalue(),'image/png')})
    assert response.status_code==200,response.text
    with m.db() as c:
        row=c.execute('SELECT photos FROM reports WHERE id=%s',(response.json()['id'],)).fetchone()
    assert len(row['photos'])==1 and (m.photo_dir()/row['photos'][0]).is_file()


def test_uncertain_commit_and_outage_never_erases_photos(live,data,monkeypatch):
    import io,psycopg
    from contextlib import contextmanager
    from PIL import Image
    original=m.db;calls=0
    @contextmanager
    def interrupted():
        nonlocal calls
        calls+=1;current=calls
        if current==3:raise psycopg.OperationalError('synthetic recovery lookup unavailable')
        with original() as connection:yield connection
        if current==2:raise psycopg.OperationalError('synthetic lost COMMIT acknowledgement')
    image=io.BytesIO();Image.new('RGB',(40,40)).save(image,'PNG')
    key=str(uuid.uuid4())
    with monkeypatch.context() as patch:
        patch.setattr(m,'db',interrupted)
        response=submit(live,data,key,photos={'photos':('synthetic.png',image.getvalue(),'image/png')})
    assert response.status_code==503 and response.headers['retry-after']=='5'
    with m.db() as c:row=c.execute('SELECT id,photos FROM reports WHERE idempotency_key=%s',(key,)).fetchone()
    assert len(row['photos'])==1 and (m.photo_dir()/row['photos'][0]).is_file()
    retry=submit(live,data,key,photos={'photos':('synthetic.png',image.getvalue(),'image/png')})
    assert retry.status_code==200 and retry.json()['id']==row['id']
