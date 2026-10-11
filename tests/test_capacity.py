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
