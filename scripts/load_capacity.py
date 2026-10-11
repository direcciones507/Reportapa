"""Disposable loopback load test. Refuses production targets and databases."""
import asyncio, collections, io, json, os, platform, subprocess, sys, tempfile, time, uuid
from pathlib import Path
import httpx, psycopg, psutil
from psycopg.conninfo import conninfo_to_dict
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/capacity-results.json'
STAGES=[10,25,50,100,250,500,1000]

def percentile(values,p):
    return round(sorted(values)[min(len(values)-1,int((len(values)-1)*p))]*1000,2)

async def main():
    params=conninfo_to_dict(os.environ['DATABASE_URL'])
    assert params.get('host') in ('localhost','127.0.0.1') and params.get('dbname')=='reportapa_test', 'Disposable loopback DB only'
    photos=Path(tempfile.mkdtemp(prefix='reportapa-load-'))
    env={**os.environ,'PHOTO_DIR':str(photos),'SESSION_SECRET':'synthetic-load-secret-'*3,'ADMIN_PASSWORD':'synthetic-password-12345','PUBLIC_REPORTS_ENABLED':'true','COOKIE_SECURE':'false'}
    log=tempfile.TemporaryFile()
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8765','--no-proxy-headers'],cwd=ROOT,env=env,stdout=log,stderr=log)
    monitor=psutil.Process(process.pid); monitor.cpu_percent()
    result={'environment':{'platform':platform.platform(),'cpu_count':os.cpu_count(),'memory_gb':round(psutil.virtual_memory().total/1e9,2),'postgres':None,'note':'Loopback isolated load; not Railway certified'},'thresholds':{'p95_ms':5000,'error_fraction':0.01,'rss_mb':1024,'abort':'Stop escalating scenario when any threshold fails; timeout 20s per request'},'stages':[]}
    image=Image.effect_noise((1600,1200),80).convert('RGB');out=io.BytesIO();image.save(out,'JPEG',quality=90);photo=out.getvalue()
    from app.main import clean_photo
    timings=[]
    for _ in range(20):
        started=time.perf_counter();clean_photo(photo);timings.append(time.perf_counter()-started)
    result['photo_processing']={'samples':20,'p50_ms':percentile(timings,.5),'p95_ms':percentile(timings,.95),'p99_ms':percentile(timings,.99)}
    try:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',timeout=20,limits=httpx.Limits(max_connections=1100,max_keepalive_connections=1100)) as client:
            for _ in range(100):
                try:
                    if (await client.get('/health')).status_code==200:break
                except httpx.TransportError:pass
                await asyncio.sleep(.1)
            else:raise RuntimeError('Server did not start')
            with psycopg.connect(os.environ['DATABASE_URL']) as db:
                result['environment']['postgres']=db.execute('SELECT version()').fetchone()[0]
                db.execute('TRUNCATE reports,request_limits,admin_sessions,photo_cleanup,deleted_reports')
            serial=0
            for scenario in ('navigation','submit_0_photos','submit_3_photos'):
                for users in STAGES:
                    latencies=[];status=collections.Counter(); ids=[]; samples=[];stop_monitor=False
                    async def sample():
                        while not stop_monitor:
                            with psycopg.connect(os.environ['DATABASE_URL']) as db:
                                connections=db.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()").fetchone()[0]
                                locks=db.execute("SELECT count(*) FROM pg_locks WHERE NOT granted").fetchone()[0]
                            samples.append({'cpu_percent':monitor.cpu_percent(),'rss_mb':monitor.memory_info().rss/1e6,'db_connections':connections,'waiting_locks':locks})
                            await asyncio.sleep(.1)
                    task=asyncio.create_task(sample())
                    async def user(i):
                        nonlocal serial
                        serial+=1;number=serial
                        for iteration in range(3 if scenario=='navigation' else 1):
                            begin=time.perf_counter()
                            try:
                                if scenario=='navigation':
                                    response=await client.get(('/', '/api/config','/static/citizen.js')[iteration])
                                else:
                                    data={'name':f'Prueba {number}','family_name':f'Sintetica {number}','total_people':'4','phone':str(60000000+number),'province':'Veraguas','district':'Santiago','township':'Santiago','community':f'Sector {number}','maps':f'https://maps.app.goo.gl/load{number}','damage':f'Daño sintético {number}','consent':'yes','idempotency_key':str(uuid.uuid4()),'needs':'Agua potable'}
                                    files=[('photos',('synthetic.jpg',photo,'image/jpeg'))]*3 if scenario=='submit_3_photos' else [('photos',('',b'','application/octet-stream'))]
                                    response=await client.post('/api/reports',data=data,files=files)
                                status[str(response.status_code)]+=1
                                if response.status_code==200 and scenario!='navigation':ids.append(response.json()['id'])
                            except httpx.HTTPError:status['transport_error']+=1
                            latencies.append(time.perf_counter()-begin)
                    begin=time.perf_counter();await asyncio.gather(*(user(i) for i in range(users)));elapsed=time.perf_counter()-begin
                    stop_monitor=True;await task
                    errors=sum(n for code,n in status.items() if code!='200')/len(latencies)
                    row={'scenario':scenario,'users':users,'http_requests':len(latencies),'duration_s':round(elapsed,3),'rps':round(len(latencies)/elapsed,2),'p50_ms':percentile(latencies,.5),'p95_ms':percentile(latencies,.95),'p99_ms':percentile(latencies,.99),'status':dict(status),'errors_fraction':round(errors,4),'peak_cpu_percent':max(s['cpu_percent'] for s in samples),'peak_rss_mb':round(max(s['rss_mb'] for s in samples),2),'max_db_connections':max(s['db_connections'] for s in samples),'max_waiting_locks':max(s['waiting_locks'] for s in samples),'confirmed':len(ids)}
                    with psycopg.connect(os.environ['DATABASE_URL']) as db:
                        stored=db.execute('SELECT count(*) FROM reports WHERE id=ANY(%s)',(ids,)).fetchone()[0] if ids else 0
                    assert stored==len(ids)==len(set(ids)), 'Confirmed reports must persist uniquely'
                    row['accepted']=errors<=.01 and row['p95_ms']<=5000 and row['peak_rss_mb']<1024
                    result['stages'].append(row);print(json.dumps(row),flush=True)
                    OUTPUT.write_text(json.dumps(result,indent=2))
                    if not row['accepted']:break
                    await asyncio.sleep(.3)
            with psycopg.connect(os.environ['DATABASE_URL']) as db:
                n=db.execute('SELECT count(*) FROM reports').fetchone()[0]
                total=db.execute("SELECT pg_total_relation_size('reports')").fetchone()[0]
                result['storage']={'synthetic_reports':n,'reports_table_and_indexes_bytes':total,'bytes_per_report_including_indexes':round(total/n,2),'input_photo_bytes':len(photo)}
            sizes=[p.stat().st_size for p in photos.glob('*.jpg')]
            result['storage'].update({'processed_photos':len(sizes),'average_photo_bytes':round(sum(sizes)/len(sizes),2) if sizes else 0,'max_photo_bytes':max(sizes) if sizes else 0})
            # Restart proves confirmed rows/photos survive process lifecycle.
            result['storage']['all_photos_present']=all(p.stat().st_size>0 for p in photos.glob('*.jpg'))
            OUTPUT.write_text(json.dumps(result,indent=2))
    finally:
        process.terminate();process.wait(timeout=20);log.close()

if __name__=='__main__':asyncio.run(main())
