import shutil, errno, logging
import os, json, uuid, hashlib, hmac, time, io, re, secrets, asyncio
from pathlib import Path
from urllib.parse import urlparse
from contextlib import asynccontextmanager, contextmanager
from psycopg_pool import ConnectionPool, PoolTimeout, TooManyRequests
from starlette.concurrency import run_in_threadpool
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, Response, JSONResponse
from starlette.datastructures import FormData
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.pdfgen import canvas
from .individual_pdf import individual_pdf
from .report_data import household, coordinates, matching_keys, COUNT_FIELDS
from .photo_maintenance import cleanup_photos
from .report_statistics import statistics, UNSPECIFIED
from .report_excel import statistical_workbook, PANAMA
from datetime import date, datetime, time as datetime_time, timedelta

logger = logging.getLogger('reportapa.storage')
PHOTO_WARNING = 'No se puede subir la foto en este momento, pero puedes seguir con tu reporte.'
ROOT = Path(__file__).resolve().parent
NEEDS = ['Agua potable','Alimentos','Pañales para bebés','Pañales para adultos','Medicamentos','Ropa y cobijas','Colchones o lugar para dormir','Materiales para reparar la vivienda','Artículos de higiene','Otra necesidad']
FIELDS = ['name','phone','province','district','township','community','maps','damage_type','damage','needs_detail']
ADMIN_USERNAME = 'Ayudapanama'
HELP_STATES = {'pendiente_confirmar':'Pendiente de confirmar','sin_ayuda':'Sin ayuda recibida','parcial':'Ayuda parcial','completa':'Ayuda completa'}
NOTICE = 'ReportaPA está para apoyarte. Si tu vivienda o familia se ha visto afectada por un sismo u otra emergencia, comparte tu situación y necesidades. Reunimos esta información para identificar comunidades afectadas y preparar reportes dirigidos a autoridades y organizaciones de apoyo, buscando facilitar la gestión de ayuda. Tu reporte contribuye a que más familias sean escuchadas. Iniciativa ciudadana independiente y gratuita.'

pool = None

@contextmanager
def db():
    if pool is None or pool.conninfo != os.environ['DATABASE_URL']:
        with psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row) as connection:
            yield connection
    else:
        with pool.connection() as connection:
            yield connection


def photo_dir():
    p = Path(os.getenv('PHOTO_DIR', '/data/private-photos')); p.mkdir(mode=0o700, parents=True, exist_ok=True); return p

def validate_runtime():
    if len(os.getenv('SESSION_SECRET','')) < 32 or len(os.getenv('ADMIN_PASSWORD','')) < 16:
        raise RuntimeError('Configure SESSION_SECRET (32+) y ADMIN_PASSWORD (16+)')
    if os.getenv('COOKIE_SECURE','true') not in ('true','false'):
        raise RuntimeError('COOKIE_SECURE debe ser true o false')
    if os.getenv('PUBLIC_REPORTS_ENABLED','false') not in ('true','false'):
        raise RuntimeError('PUBLIC_REPORTS_ENABLED debe ser true o false')
    if os.getenv('RAILWAY_ENVIRONMENT_ID'):
        mount=os.getenv('RAILWAY_VOLUME_MOUNT_PATH','')
        if not mount or not Path(mount).is_dir() or not Path(os.getenv('PHOTO_DIR','/data/private-photos')).resolve().is_relative_to(Path(mount).resolve()):
            raise RuntimeError('Configure PHOTO_DIR dentro del volumen privado persistente de Railway')
        if os.getenv('COOKIE_SECURE','true') != 'true':
            raise RuntimeError('Railway requiere COOKIE_SECURE=true y HTTPS')

@asynccontextmanager
async def lifespan(app):
    global pool
    previous_pool = pool
    validate_runtime()
    active_pool = ConnectionPool(os.environ['DATABASE_URL'], min_size=2,
                          max_size=int(os.getenv('DB_POOL_MAX','8')), timeout=10,
                          max_waiting=64, kwargs={'row_factory':dict_row,'application_name':'reportapa-web',
                          'options':'-c statement_timeout=15000 -c lock_timeout=10000'}, open=False)
    pool = active_pool
    await asyncio.to_thread(active_pool.open, wait=True)
    app.state.waiting_submissions = 0
    app.state.submissions = asyncio.Semaphore(int(os.getenv('SUBMISSION_WORKERS','8')))
    with db() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended('reportapa-migrations',2))")
        for migration in sorted((ROOT.parent/'migrations').glob('*.sql')):
            c.execute(migration.read_text())
            if migration.name == '008_responsible_cedula.sql':
                logger.info('migration_checked name=%s', migration.name)
    # Photo storage may fail independently of the family database.
    # Backfill matching keys from real legacy data; do not invent household counts.
    with db() as c:
        for report in c.execute("SELECT id,data FROM reports WHERE dedup_keys='{}'").fetchall():
            data=report['data'];data['coordinates']=coordinates(data['maps'])
            c.execute('UPDATE reports SET data=%s::jsonb,dedup_keys=%s WHERE id=%s',(json.dumps(data),matching_keys(data,signing),report['id']))
    try: await asyncio.to_thread(cleanup_photos,db,photo_dir())
    except OSError as error: logger.warning('photo_storage_unavailable stage=startup errno=%s',error.errno)
    async def maintain():
        while True:
            await asyncio.sleep(30)
            try:
                await asyncio.to_thread(cleanup_photos,db,photo_dir())
                await asyncio.to_thread(prune_limits)
            except (psycopg.Error,OSError): pass  # Retry after transient database interruption.
    worker=asyncio.create_task(maintain())
    try: yield
    finally:
        worker.cancel()
        try: await worker
        except asyncio.CancelledError: pass
        await asyncio.to_thread(active_pool.close)
        pool = previous_pool

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

async def admission(request, call_next):
    if request.url.path != '/api/reports' or request.method != 'POST':
        return await call_next(request)
    gate = getattr(app.state,'submissions',None)
    if gate is None: return await call_next(request)
    busy = JSONResponse({'detail':'Servicio temporalmente ocupado; vuelva a intentar.'},
                        status_code=503,headers={'Retry-After':'5','Cache-Control':'no-store'})
    if app.state.waiting_submissions >= 128: return busy
    app.state.waiting_submissions += 1
    acquired = False
    try:
        await asyncio.wait_for(gate.acquire(),timeout=15)
        acquired = True
        return await call_next(request)
    except asyncio.TimeoutError:
        return busy
    finally:
        app.state.waiting_submissions -= 1
        if acquired: gate.release()

@app.middleware('http')
async def headers(request, call_next):
    if request.method in ('POST','PATCH','DELETE'):
        maximum = 16*1024*1024 if request.url.path == '/api/reports' else 4096
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > maximum: return JSONResponse({'detail':'Solicitud demasiado grande'},status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','X-Robots-Tag':'noindex, nofollow','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    return response

app.middleware('http')(admission)

def signing(value):
    return hmac.new(os.environ['SESSION_SECRET'].encode(), value.encode(), hashlib.sha256).hexdigest()

def admin(request: Request):
    token = request.cookies.get('rpa_session','')
    try:
        expiry, nonce, signature = token.split('.')
        if int(expiry) < time.time() or not hmac.compare_digest(signing(expiry+'.'+nonce).encode(),signature.encode()): raise ValueError()
    except (ValueError, KeyError): raise HTTPException(401,'Sesión requerida')
    with db() as c:
        active=c.execute('SELECT username,credential_hash FROM admin_sessions WHERE token_hash=%s AND expires_at>now()', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not active or active['username'] != ADMIN_USERNAME or not hmac.compare_digest(active['credential_hash'],signing(os.environ['ADMIN_PASSWORD'])):
        raise HTTPException(401,'Sesión requerida')
    if request.method != 'GET' and not hmac.compare_digest(request.headers.get('x-csrf-token','').encode(), signing(token).encode()):
        raise HTTPException(403,'Solicitud inválida')
    with db() as c:
        c.execute("UPDATE admin_sessions SET expires_at=LEAST(to_timestamp(%s),now()+interval '15 minutes') WHERE token_hash=%s AND expires_at>now()", (int(expiry), hashlib.sha256(token.encode()).hexdigest()))
    return token

def limit(request, action, maximum, identity=None):
    # Use the direct peer; do not trust client-supplied forwarding headers.
    key = signing(action+':'+(identity if identity is not None else (request.client.host if request.client else 'unknown')))
    with db() as c:
        r = c.execute("INSERT INTO request_limits(key,count) VALUES (%s,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN request_limits.started_at < now()-interval '15 minutes' THEN 1 ELSE request_limits.count+1 END, started_at=CASE WHEN request_limits.started_at < now()-interval '15 minutes' THEN now() ELSE request_limits.started_at END RETURNING count",(key,)).fetchone()

    if r['count'] > maximum: raise HTTPException(429,'Demasiados intentos. Espere 15 minutos.')

def prune_limits():
    with db() as c: c.execute("DELETE FROM request_limits WHERE started_at < now()-interval '1 day'")

def validate(raw, allow_missing_family=False):
    data = {k: str(raw.get(k,'')).strip() for k in FIELDS}
    for k in FIELDS:
        if k not in ('needs_detail','damage_type','maps') and not data[k]: raise HTTPException(422,'Complete los campos obligatorios')
        if len(data[k]) > (1500 if k in ('damage','needs_detail') else 300): raise HTTPException(422,'Campo demasiado largo')
    if not re.fullmatch(r'[+0-9() .-]+',data['phone']): raise HTTPException(422,'Teléfono de Panamá inválido')
    data['phone'] = re.sub(r'[^0-9]','',data['phone'])
    if len(data['phone']) == 11 and data['phone'].startswith('507'): data['phone'] = data['phone'][3:]
    if not re.fullmatch(r'[2-9][0-9]{6,7}',data['phone']): raise HTTPException(422,'Teléfono de Panamá inválido')
    if data['maps']:
        try:
            u = urlparse(data['maps'])
            port = u.port
        except ValueError: raise HTTPException(422,'Enlace Maps inválido')
        if u.scheme != 'https' or u.username or u.password or port or u.hostname not in ('maps.app.goo.gl','goo.gl','www.google.com','google.com','maps.google.com'):
            raise HTTPException(422,'Use un enlace HTTPS compartido de Google Maps')
        if u.hostname in ('google.com','www.google.com') and not u.path.startswith('/maps'): raise HTTPException(422,'Enlace Maps inválido')
        if u.hostname == 'goo.gl' and not u.path.startswith('/maps/'): raise HTTPException(422,'Enlace Maps inválido')
        if not u.path.strip('/'): raise HTTPException(422,'Enlace Maps incompleto')
    needs = raw.get('needs',[])
    if not isinstance(needs,list) or any(n not in NEEDS for n in needs): raise HTTPException(422,'Necesidad inválida')
    data['needs'] = list(dict.fromkeys(needs))
    cedula = raw.get('cedula')
    if cedula is not None:
        if not isinstance(cedula, str): raise HTTPException(422,'Número de cédula inválido')
        cedula = cedula.strip().upper()
        if cedula and not re.fullmatch(r'[A-Z0-9]{1,6}-[0-9]{1,6}-[0-9]{1,6}', cedula):
            raise HTTPException(422,'Número de cédula inválido; use tres grupos separados por guiones (ejemplo: 8-123-456)')
        if cedula: data['cedula'] = cedula
    mode=str(raw.get('reporting_for_self','yes')).strip()
    if mode not in ('yes','no'): raise HTTPException(422,'Indique quién realiza el reporte')
    reporter=str(raw.get('reporter_name','')).strip()
    if len(reporter)>300: raise HTTPException(422,'Nombre de quien reporta demasiado largo')
    if mode=='no' and not reporter: raise HTTPException(422,'Indique el nombre de quien realiza el reporte')
    data['reporting_for_self']=mode
    data['reporter_name']=reporter if mode=='no' else ''
    data.update(household(raw, allow_missing_family=allow_missing_family));data['coordinates']=coordinates(data['maps'])
    return data

def clean_photo(content):
    if len(content) > 5*1024*1024: raise HTTPException(422,'Cada foto debe pesar menos de 5 MB')
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in ('JPEG','PNG','WEBP') or im.width*im.height > 25_000_000: raise ValueError()
            im = ImageOps.exif_transpose(im); im.thumbnail((2000,2000))
            out = io.BytesIO(); im.convert('RGB').save(out,'JPEG',quality=85); return out.getvalue()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError): raise HTTPException(422,'Foto inválida: use JPG, PNG o WebP')

@app.get('/og-image.png')
def social_preview_image():
    # Serve a predictable social-card size without changing the uploaded original.
    with Image.open(ROOT/'static/og-image.png') as original:
        artwork = ImageOps.exif_transpose(original).convert('RGBA')
        artwork.thumbnail((1200, 630), Image.Resampling.LANCZOS)
        card = Image.new('RGBA', (1200, 630), (255, 255, 255, 255))
        card.alpha_composite(artwork, ((1200-artwork.width)//2, (630-artwork.height)//2))
        output = io.BytesIO()
        card.convert('RGB').save(output, format='PNG', optimize=True)
    return Response(content=output.getvalue(), media_type='image/png', headers={'Cache-Control':'public, max-age=3600'})

@app.get('/')
def home(): return FileResponse(ROOT/'static/index.html')
@app.get('/entrega-ayuda')
def aid_page(): return FileResponse(ROOT/'static/aid.html')
@app.get('/admin')
def panel(): return FileResponse(ROOT/'static/admin.html')
@app.get('/health')
def health():
    with db() as c: c.execute('SELECT 1')
    return {'status':'ok'}
@app.get('/api/config')
def config(): return {'enabled':os.getenv('PUBLIC_REPORTS_ENABLED','false') == 'true','needs':NEEDS,'notice':NOTICE}
async def json_payload(request):
    try: return await request.json()
    except (ValueError,UnicodeDecodeError): raise HTTPException(422,'Solicitud inválida')

@app.post('/api/admin/login')
async def login(request: Request):
    limit(request,'login',10)
    data = await json_payload(request)
    if not isinstance(data,dict): raise HTTPException(422,'Solicitud inválida')
    username=data.get('username',''); password=data.get('password','')
    if not isinstance(username,str) or not isinstance(password,str): raise HTTPException(401,'Credenciales inválidas')
    user_ok=hmac.compare_digest(username.encode(),ADMIN_USERNAME.encode())
    password_ok=hmac.compare_digest(password.encode(),os.environ['ADMIN_PASSWORD'].encode())
    if not (user_ok and password_ok): raise HTTPException(401,'Credenciales inválidas')
    expiry=int(time.time()+3600)
    value = str(expiry)+'.'+secrets.token_hex(24); token = value+'.'+signing(value)
    with db() as c:
        c.execute('DELETE FROM admin_sessions WHERE expires_at<=now()')
        c.execute('INSERT INTO admin_sessions(token_hash,username,expires_at,credential_hash) VALUES (%s,%s,to_timestamp(%s),%s)',
                  (hashlib.sha256(token.encode()).hexdigest(),ADMIN_USERNAME,min(expiry,int(time.time()+900)),signing(os.environ['ADMIN_PASSWORD'])))
    response = JSONResponse({'csrf':signing(token)})
    response.set_cookie('rpa_session',token,httponly=True,secure=os.getenv('COOKIE_SECURE','true') == 'true',samesite='strict',max_age=3600,path='/'); return response
@app.get('/api/admin/session')
def session(token=Depends(admin)): return {'csrf':signing(token),'username':ADMIN_USERNAME}
@app.post('/api/admin/logout')
def logout(token=Depends(admin)):
    with db() as c: c.execute('DELETE FROM admin_sessions WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),))
    r = JSONResponse({'ok':True}); r.delete_cookie('rpa_session',path='/'); return r

@app.post('/api/integrations/reports')
async def submit_integrated_report(request: Request):
    """Opt-in authenticated integration; disabled until a dedicated secret is configured."""
    secret = os.getenv('REPORTAPA_INTEGRATION_TOKEN', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Integración no configurada')
    supplied = request.headers.get('authorization', '')
    expected = 'Bearer ' + secret
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Credenciales de integración inválidas')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'Se requiere JSON')
    if request.headers.get('content-length', '0').isdigit() and int(request.headers.get('content-length', '0')) > 32768:
        raise HTTPException(413, 'Solicitud demasiado grande')
    if len(await request.body()) > 32768:
        raise HTTPException(413, 'Solicitud demasiado grande')
    try:
        raw = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, 'JSON inválido')
    if not isinstance(raw, dict):
        raise HTTPException(422, 'Se requiere un objeto JSON')
    try:
        key = str(uuid.UUID(str(raw.get('idempotency_key', ''))))
    except ValueError:
        raise HTTPException(422, 'Clave de envío inválida')
    if raw.get('consent') != 'yes':
        raise HTTPException(422, 'Se requiere consentimiento registrado')
    data = validate(raw, allow_missing_family=True)
    fields = [(k, str(v)) for k, v in raw.items() if isinstance(v, (str, int, float)) and k != 'needs']
    fields.extend(('needs', n) for n in data['needs'])
    form = FormData(fields)
    try:
        return await run_in_threadpool(persist_report, request, form, key, data)
    except (PoolTimeout, TooManyRequests, psycopg.OperationalError, psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable):
        raise HTTPException(503, 'Servicio temporalmente ocupado; vuelva a intentar.', headers={'Retry-After':'5'})


@app.post('/api/admin/reports/paper')
async def submit_paper(request: Request, token=Depends(admin)):
    """Manual transcription of paper forms, using the existing persistence and deduplication."""
    form = await request.form(max_files=1, max_fields=40)
    try:
        try: key = str(uuid.UUID(str(form.get('idempotency_key',''))))
        except ValueError: raise HTTPException(422,'Clave de envío inválida')
        raw = dict(form)
        raw['needs'] = form.getlist('needs')
        data = validate(raw, allow_missing_family=True)
        if form.get('consent') != 'yes':
            raise HTTPException(422,'Debe constar la autorización privada del formulario en papel')
        return await run_in_threadpool(persist_report,request,form,key,data)
    except (PoolTimeout, TooManyRequests, psycopg.OperationalError, psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable):
        raise HTTPException(503,'Servicio temporalmente ocupado; vuelva a intentar.',headers={'Retry-After':'5'})
    finally:
        await form.close()


@app.post('/api/reports')
async def submit(request: Request):
    if os.getenv('PUBLIC_REPORTS_ENABLED','false') != 'true': raise HTTPException(503,'Recepción de reportes aún no habilitada')
    form = await request.form(max_files=1,max_fields=40)
    try:
        if form.get('website'): raise HTTPException(422,'Solicitud inválida')
        try: key = str(uuid.UUID(str(form.get('idempotency_key',''))))
        except ValueError: raise HTTPException(422,'Clave de envío inválida')
        if str(form.get('province', '')).strip().casefold() != 'veraguas':
            raise HTTPException(422, 'Este formulario solo está habilitado para la provincia de Veraguas.')
        raw = dict(form); raw['needs'] = form.getlist('needs'); data = validate(raw)
        if form.get('consent') != 'yes': raise HTTPException(422,'Debe autorizar el uso privado de los datos')
        return await run_in_threadpool(persist_report,request,form,key,data)
    except (PoolTimeout, TooManyRequests, psycopg.OperationalError, psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable):
        raise HTTPException(503,'Servicio temporalmente ocupado; vuelva a intentar.',headers={'Retry-After':'5'})
    finally:
        await form.close()


def persist_report(request,form,key,data):
    # Families sharing Wi-Fi/proxy have independent counters; no forwarding header trust.
    limit(request,'submit',20,identity=data['phone'])
    photos = []
    for f in form.getlist('photos'):
        if hasattr(f,'read') and f.filename:
            photos.append(clean_photo(f.file.read(5*1024*1024+1)))
    if len(photos)>1: raise HTTPException(422,'Máximo una foto')
    digest = hashlib.sha256(json.dumps(data,sort_keys=True).encode()+b''.join(hashlib.sha256(p).digest() for p in photos)).hexdigest()
    fingerprint = signing(data['phone']+'|'+data['maps'].rstrip('/')) if data['maps'] else signing('no-map|'+key)
    dedup=matching_keys(data,signing)
    saved = []; photo_failed = False; pending_photo_cleanup=[]
    try:
        with db() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
            for match_key in sorted(dedup):
                c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,1))',(match_key,))
            existing = c.execute('SELECT id,request_hash,data,photo_upload_failed FROM reports WHERE idempotency_key=%s',(key,)).fetchone()
            if existing:
                if existing['request_hash'] != digest and not (existing['photo_upload_failed'] and existing['data']==data): raise HTTPException(409,'La clave ya se utilizó con otro contenido')
                return report_confirmation(existing['id'],existing['photo_upload_failed'])
            identical=c.execute('SELECT 1 FROM reports WHERE request_hash=%s LIMIT 1',(digest,)).fetchone()
            if identical: raise HTTPException(409,'No se guardó otro reporte: el envío coincide exactamente con uno previo. Solicite revisión al administrador si necesita corregirlo.')
            duplicate = c.execute('SELECT 1 FROM reports WHERE dedup_keys && %s::text[] OR fingerprint=%s LIMIT 1',(dedup,fingerprint)).fetchone()
            if duplicate and form.get('new_damage') != 'yes':
                return JSONResponse({'possible_duplicate':True,'message':'Hay una coincidencia probable. Si son daños nuevos o corresponde a otra familia, confirme para enviar un nuevo reporte.'},status_code=409)
            if photos:
                try:
                    directory=photo_dir()
                    if shutil.disk_usage(directory).free < sum(map(len,photos))+32*1024*1024:
                        raise OSError(errno.ENOSPC,'photo storage reserve exhausted')
                    for photo in photos:
                        filename=uuid.uuid4().hex+'.jpg';path=directory/filename
                        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                        saved.append(filename)
                        with os.fdopen(descriptor,'wb') as output:
                            output.write(photo);output.flush();os.fsync(output.fileno())
                except OSError as error:
                    photo_failed=True
                    logger.warning('photo_storage_unavailable stage=submit errno=%s',error.errno)
                    # Only this attempt's newly created files can be removed/queued.
                    for filename in saved:
                        try: (directory/filename).unlink(missing_ok=True)
                        except OSError: pending_photo_cleanup.append(filename)
                    saved=[]
            r = c.execute('INSERT INTO reports(idempotency_key,request_hash,fingerprint,data,photos,dedup_keys,photo_upload_failed) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING id',(key,digest,fingerprint,json.dumps(data),json.dumps(saved),dedup,photo_failed)).fetchone()
        queue_partial_photos(pending_photo_cleanup)
        return report_confirmation(r['id'],photo_failed)
    except Exception as error:
        # A lost COMMIT acknowledgement must never erase photos of a saved family.
        if isinstance(error,psycopg.OperationalError):
            try:
                with db() as check:
                    confirmed=check.execute('SELECT id,request_hash,data,photo_upload_failed FROM reports WHERE idempotency_key=%s',(key,)).fetchone()
                if confirmed and (confirmed['request_hash']==digest or (confirmed['photo_upload_failed'] and confirmed['data']==data)):
                    queue_partial_photos(pending_photo_cleanup)
                    return report_confirmation(confirmed['id'],confirmed['photo_upload_failed'])
            except psycopg.Error:
                # Outcome unknown: retain private files until DB recovery/reconciliation.
                raise error
        pending=[]
        for filename in saved:
            try: (photo_dir()/filename).unlink(missing_ok=True)
            except OSError: pending.append(filename)
        if pending:
            try:
                with db() as c:
                    for filename in pending:
                        c.execute('INSERT INTO photo_cleanup(filename) VALUES (%s) ON CONFLICT DO NOTHING',(filename,))
            except psycopg.Error: pass  # Database outage: private orphan requires later reconciliation.
        raise

def queue_partial_photos(filenames):
    if not filenames: return
    # Cleanup bookkeeping must never roll back a confirmed family report.
    try:
        with db() as c:
            for filename in filenames:
                c.execute('INSERT INTO photo_cleanup(filename) VALUES (%s) ON CONFLICT DO NOTHING',(filename,))
    except (psycopg.Error,PoolTimeout,TooManyRequests):
        logger.warning('photo_cleanup_queue_unavailable partial_files=%s',len(filenames))

def report_confirmation(identifier,photo_failed=False):
    result={'id':identifier,'notice':NOTICE}
    if photo_failed: result['photo_warning']=PHOTO_WARNING
    return result

@app.get('/api/admin/storage')
def storage_metrics(token=Depends(admin)):
    with db() as c:
        total=c.execute('SELECT count(*) AS n FROM reports').fetchone()['n']
    result={'total_reports':total,'photographs':None,'used_bytes':None,'available_bytes':None,'total_bytes':None,'occupation_percent':None,'alert':None,'storage_available':False,'measured_at':time.time()}
    try:
        directory=photo_dir();disk=shutil.disk_usage(directory)
        # Scan actual private files; historical reports can still have multiple photos.
        with os.scandir(directory) as entries:
            count=sum(1 for entry in entries if re.fullmatch(r'[a-f0-9]{32}\.jpg',entry.name) and entry.is_file(follow_symlinks=False))
        occupied=100*(disk.total-disk.free)/disk.total
        result.update(photographs=count,used_bytes=disk.total-disk.free,available_bytes=disk.free,total_bytes=disk.total,occupation_percent=round(occupied,2),alert=next((level for level in (95,85,70) if occupied>=level),None),storage_available=True)
    except OSError as error:
        logger.warning('photo_storage_unavailable stage=metrics errno=%s',error.errno)
    return result

def rows(request, all_rows=False, page=None):
    clauses=[]; values=[]
    if not all_rows:
        archive=request.query_params.get('archive','active')
        if archive not in ('active','archived','all'): raise HTTPException(422,'Filtro de archivo inválido')
        if archive!='all': clauses.append('archived_at IS '+('NULL' if archive=='active' else 'NOT NULL'))
        for key in ('province','district','township','community','status','need','estado_ayuda','damage_type'):
            value = request.query_params.get(key,'').strip()
            if not value: continue
            if key in ('status','estado_ayuda'):
                if key == 'estado_ayuda' and value not in HELP_STATES: raise HTTPException(422,'Estado de ayuda inválido')
                if key == 'status' and value not in ('pendiente','contactado','visitado'): raise HTTPException(422,'Estado operativo inválido')
                clauses.append(key+'=%s')
            elif key == 'need':
                if value == UNSPECIFIED:
                    clauses.append("CASE WHEN jsonb_typeof(data->'needs')='array' THEN data->'needs'='[]'::jsonb OR EXISTS (SELECT 1 FROM jsonb_array_elements(data->'needs') AS item(value) WHERE coalesce(item.value #>> '{}','') <> ALL(%s::text[])) ELSE true END")
                    values.append(NEEDS)
                    continue
                clauses.append("data->'needs' ? %s")
            elif key in ('province','district','township','community','damage_type') and value == UNSPECIFIED:
                clauses.append("coalesce(nullif(btrim(data->>%s),''),'No especificada')=%s"); values.append(key)
            else: clauses.append('data->>%s = %s'); values.append(key)
            values.append(value)
        search=request.query_params.get('search','').strip()
        if len(search)>120: raise HTTPException(422,'Búsqueda demasiado larga')
        if search:
            pattern='%'+search.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
            clauses.append("(id ILIKE %s ESCAPE '!' OR data->>'name' ILIKE %s ESCAPE '!' OR data->>'community' ILIKE %s ESCAPE '!')")
            values.extend((pattern,pattern,pattern))
        period = {}
        for key in ('date_from','date_to'):
            value = request.query_params.get(key,'').strip()
            if not value: continue
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): raise ValueError
                period[key] = date.fromisoformat(value)
            except ValueError: raise HTTPException(422,'Período inválido; use fechas AAAA-MM-DD')
        if period.get('date_from') and period.get('date_to') and period['date_from'] > period['date_to']:
            raise HTTPException(422,'La fecha inicial no puede ser posterior a la final')
        if 'date_from' in period:
            clauses.append('created_at >= %s'); values.append(datetime.combine(period['date_from'],datetime_time.min,PANAMA))
        if 'date_to' in period:
            if period['date_to'] == date.max: raise HTTPException(422,'Fecha final fuera de rango')
            clauses.append('created_at < %s'); values.append(datetime.combine(period['date_to']+timedelta(days=1),datetime_time.min,PANAMA))
        group = request.query_params.get('tracking','').strip()
        attended = "(estado_ayuda IN ('parcial','completa') AND ayuda_actualizada_at IS NOT NULL)"
        if group:
            if group not in ('pending','followup','attended'): raise HTTPException(422,'Filtro de seguimiento inválido')
            clauses.append(attended if group == 'attended' else
                           'NOT '+attended+(' AND status=\'pendiente\'' if group == 'pending' else " AND status IN ('contactado','visitado')"))
    sql = 'SELECT * FROM reports'+(' WHERE '+' AND '.join(clauses) if clauses else '')+" ORDER BY data->>'province',data->>'district',data->>'township',created_at,id"
    with db() as c:
        if page is None: return c.execute(sql,values).fetchall()
        total=c.execute('SELECT count(*) AS n FROM reports'+(' WHERE '+' AND '.join(clauses) if clauses else ''),values).fetchone()['n']
        return {'total':total,'reports':c.execute(sql+' LIMIT 20 OFFSET %s',[*values,(page-1)*20]).fetchall()}
@app.get('/api/admin/reports')
def reports(request: Request, token=Depends(admin)):
    try: page=max(1,int(request.query_params.get('page','1')))
    except ValueError: raise HTTPException(422,'Página inválida')
    if request.query_params.get('include_statistics') == 'true':
        # One read supplies the list and all totals: no count joins or page-only statistics.
        records=rows(request)
        return {'total':len(records),'reports':records[(page-1)*20:page*20],
                'statistics':statistics(records),'statistics_at':datetime.now(PANAMA)}
    return rows(request,page=page)
@app.patch('/api/admin/reports/{report_id}')
async def status(report_id: str, request: Request, token=Depends(admin)):
    payload = await json_payload(request)
    if not isinstance(payload,dict) or not payload or set(payload)-{'status','estado_ayuda','observacion','archived'}:
        raise HTTPException(422,'Cambio inválido')
    if 'status' in payload and payload['status'] not in ('pendiente','contactado','visitado'):
        raise HTTPException(422,'Estado operativo inválido')
    if 'estado_ayuda' in payload and (not isinstance(payload['estado_ayuda'],str) or payload['estado_ayuda'] not in HELP_STATES):
        raise HTTPException(422,'Estado de ayuda inválido')
    if 'observacion' in payload and 'estado_ayuda' not in payload: raise HTTPException(422,'Seleccione el estado de ayuda')
    if 'archived' in payload and not isinstance(payload['archived'],bool): raise HTTPException(422,'Archivo inválido')
    note = payload.get('observacion')
    if note is not None and (not isinstance(note,str) or len(note)>500): raise HTTPException(422,'Observación: máximo 500 caracteres')
    with db() as c:
        report=c.execute('SELECT * FROM reports WHERE id=%s FOR UPDATE',(report_id,)).fetchone()
        if not report: raise HTTPException(404)
        if 'archived' in payload:
            if payload['archived'] and not report['archived_at']:
                c.execute('UPDATE reports SET archived_at=now(),archived_by=%s WHERE id=%s',(ADMIN_USERNAME,report_id))
            elif not payload['archived']:
                c.execute('UPDATE reports SET archived_at=NULL,archived_by=NULL WHERE id=%s',(report_id,))
        if 'status' in payload: c.execute('UPDATE reports SET status=%s WHERE id=%s',(payload['status'],report_id))
        if 'estado_ayuda' in payload:
            note=report['ayuda_observacion'] if note is None else note.strip()
            if payload['estado_ayuda'] != report['estado_ayuda'] or note != report['ayuda_observacion']:
                # The authenticated session belongs exclusively to the configured owner.
                c.execute("""UPDATE reports SET estado_ayuda=%s, ayuda_observacion=%s,
                    ayuda_actualizada_at=now(), ayuda_admin=%s,
                    ayuda_historial=ayuda_historial || jsonb_build_array(jsonb_build_object(
                      'anterior',estado_ayuda,'estado',%s::text,'fecha',now(),
                      'observacion',%s::text,'administrador',%s::text)) WHERE id=%s""",
                    (payload['estado_ayuda'],note,ADMIN_USERNAME,payload['estado_ayuda'],note,ADMIN_USERNAME,report_id))
    return {'ok':True}

@app.delete('/api/admin/reports/{report_id}')
async def delete_report(report_id: str, request: Request, token=Depends(admin)):
    payload=await json_payload(request)
    if not isinstance(payload,dict) or payload.get('confirm') != 'ELIMINAR '+report_id:
        raise HTTPException(422,'Confirme escribiendo ELIMINAR seguido del número de reporte')
    with db() as c:
        report=c.execute('SELECT photos FROM reports WHERE id=%s FOR UPDATE',(report_id,)).fetchone()
        if not report: raise HTTPException(404)
        for name in report['photos']:
            c.execute('INSERT INTO photo_cleanup(filename) VALUES (%s) ON CONFLICT DO NOTHING',(name,))
        c.execute('INSERT INTO deleted_reports(id) VALUES (%s) ON CONFLICT DO NOTHING',(report_id,))
        c.execute('DELETE FROM reports WHERE id=%s',(report_id,))
    # After commit, the private routes can no longer serve the deleted photos.
    try:
        await asyncio.to_thread(cleanup_photos,db,photo_dir())
        with db() as c:
            pending=c.execute('SELECT count(*) AS n FROM photo_cleanup WHERE filename=ANY(%s)',(report['photos'],)).fetchone()['n']
    except (psycopg.Error,OSError):
        return JSONResponse({'deleted':True,'photos_pending':len(report['photos']),'message':'Datos eliminados. No se pudo verificar la limpieza física; se reintentará automáticamente.'},status_code=202)
    return JSONResponse({'deleted':True,'photos_pending':pending,'message':'Datos eliminados. '+('Limpieza física de fotos pendiente; se reintentará automáticamente.' if pending else 'Fotografías eliminadas.')},status_code=202 if pending else 200)

@app.get('/api/admin/reports/{report_id}/pdf')
def report_pdf(report_id: str, token=Depends(admin)):
    with db() as c: report=c.execute('SELECT * FROM reports WHERE id=%s',(report_id,)).fetchone()
    if not report: raise HTTPException(404)
    content=individual_pdf(report,photo_dir(),HELP_STATES)
    return Response(content,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="REPORTAPA_{report["id"]}_FICHA.pdf"'})
@app.get('/api/admin/reports/{report_id}/photos/{filename}')
def photo(report_id: str, filename: str, token=Depends(admin)):
    with db() as c: r=c.execute('SELECT photos FROM reports WHERE id=%s',(report_id,)).fetchone()
    if not r or filename not in r['photos'] or not re.fullmatch(r'[a-f0-9]{32}\.jpg',filename): raise HTTPException(404)
    path=photo_dir()/filename
    if not path.is_file(): raise HTTPException(404,'Foto no disponible')
    return FileResponse(path,media_type='image/jpeg')

def workbook(records, filters, anonymous=False, include_personal=True):
    return statistical_workbook(records,filters,HELP_STATES,anonymous,include_personal)
@app.get('/api/admin/export/{kind}')
def export(kind: str, request: Request, token=Depends(admin)):
    if kind not in ('master','area','anonymous','summary','erasures'): raise HTTPException(404)
    if kind=='erasures':
        with db() as c: ledger=c.execute('SELECT id,deleted_at FROM deleted_reports ORDER BY deleted_at').fetchall()
        content=json.dumps([{'id':r['id'],'deleted_at':r['deleted_at'].isoformat()} for r in ledger])
        return Response(content,media_type='application/json',headers={'Content-Disposition':'attachment; filename=REPORTAPA_ELIMINACIONES.json'})
    records=rows(request,all_rows=kind=='master'); filters='Todos los reportes' if kind=='master' else json.dumps(dict(request.query_params),ensure_ascii=False)
    if kind=='summary':
        out=io.BytesIO(); pdf=canvas.Canvas(out); y=790
        for line in ['ReportaPA - resumen anonimizado',time.strftime('Fecha de corte: %Y-%m-%d'),f'Total de registros: {len(records)}']:
            pdf.drawString(40,y,line); y-=24
        counts={}
        for r in records:
            key=(r['data']['province'],r['status']); counts[key]=counts.get(key,0)+1
        for (province,state),count in sorted(counts.items()):
            if y<60: pdf.showPage(); y=790
            pdf.drawString(40,y,f'{province} / {state}: {count}'); y-=20
        pdf.save(); return Response(out.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="REPORTAPA_RESUMEN.pdf"'})
    scope='MASTER' if kind=='master' else re.sub(r'[^A-Za-z0-9_-]','_', '_'.join(request.query_params.get(k,'') for k in ('province','district','township','community'))).strip('_') or kind.upper()
    filename=f'REPORTAPA_{scope[:100]}_{time.strftime("%Y-%m-%d")}.xlsx'
    personal=request.query_params.get('include_personal','false')
    if personal not in ('true','false'): raise HTTPException(422,'Opción de datos personales inválida')
    return Response(workbook(records,filters,kind=='anonymous',personal=='true'),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})


# Register isolated aid-delivery endpoints after existing dependencies are defined.
from .aid_delivery import install as install_aid_delivery
install_aid_delivery(app, db, admin, limit, signing, json_payload)


@app.post('/mcp')
async def mcp_transport(request: Request):
    """Authenticated MCP JSON-RPC entry point; writes remain disabled."""
    # OAuth discovery probes may POST without JSON; challenge first so ChatGPT
    # can discover the authorization server rather than receiving HTTP 415.
    from .mcp_oauth import verify_mcp_access_token
    from jwt.exceptions import InvalidTokenError, PyJWKClientError
    supplied = request.headers.get('authorization', '')
    challenge = (
        'Bearer realm="ReportaPA", error="invalid_token", '
        'resource_metadata="https://reportapa.online/.well-known/oauth-protected-resource"'
    )
    if not supplied.startswith('Bearer '):
        return JSONResponse({'error': 'Autenticación requerida'}, status_code=401,
                            headers={'WWW-Authenticate': challenge, 'Cache-Control': 'no-store'})
    try:
        verify_mcp_access_token(supplied[7:])
    except RuntimeError:
        raise HTTPException(503, 'Proveedor OAuth no configurado')
    except (InvalidTokenError, PyJWKClientError, ValueError):
        return JSONResponse({'error': 'Token inválido'}, status_code=401,
                            headers={'WWW-Authenticate': challenge, 'Cache-Control': 'no-store'})
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'Se requiere JSON')
    if len(await request.body()) > 32768:
        raise HTTPException(413, 'Solicitud demasiado grande')
    try:
        payload = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, 'JSON inválido')
    if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0':
        raise HTTPException(422, 'JSON-RPC 2.0 requerido')
    method = payload.get('method')
    request_id = payload.get('id')
    if method == 'notifications/initialized':
        return Response(status_code=202)
    if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
        raise HTTPException(422, 'Identificador JSON-RPC inválido')
    if method == 'initialize':
        result = {
            'protocolVersion': '2025-03-26',
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': {'name': 'ReportaPA', 'version': '0.1.0'},
        }
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        from .mcp_contract import REGISTER_REPORT_TOOL
        result = {'tools': [REGISTER_REPORT_TOOL]}
    elif method == 'tools/call':
        from .mcp_contract import REGISTER_REPORT_TOOL
        params = payload.get('params')
        if not isinstance(params, dict) or params.get('name') != REGISTER_REPORT_TOOL['name']:
            return JSONResponse({'jsonrpc': '2.0', 'id': request_id,
                                 'error': {'code': -32602, 'message': 'Herramienta desconocida'}},
                                headers={'Cache-Control': 'no-store'})
        raw = params.get('arguments')
        schema = REGISTER_REPORT_TOOL['inputSchema']
        if (not isinstance(raw, dict) or set(raw) - set(schema['properties'])
                or any(k not in raw for k in schema['required'])
                or any(not isinstance(raw[k], str) or not raw[k].strip()
                       for k in schema['required'] if k not in ('needs', 'total_people'))
                or not isinstance(raw.get('total_people'), int)
                or isinstance(raw.get('total_people'), bool)
                or not 1 <= raw['total_people'] <= 1000
                or not isinstance(raw.get('needs'), list)
                or any(not isinstance(n, str) for n in raw['needs'])):
            return JSONResponse({'jsonrpc': '2.0', 'id': request_id,
                                 'error': {'code': -32602, 'message': 'Argumentos inválidos'}},
                                headers={'Cache-Control': 'no-store'})
        try:
            key = str(uuid.UUID(raw['idempotency_key']))
            if raw['consent'] != 'yes':
                raise ValueError('Consentimiento requerido')
            data = validate(raw, allow_missing_family=True)
            fields = [(k, str(v)) for k, v in raw.items()
                      if isinstance(v, (str, int, float)) and k != 'needs']
            fields.extend(('needs', n) for n in data['needs'])
            form = FormData(fields)
            saved = await run_in_threadpool(persist_report, request, form, key, data)
            if isinstance(saved, JSONResponse):
                return JSONResponse({'jsonrpc': '2.0', 'id': request_id,
                                     'result': {'isError': True, 'content': [
                                         {'type': 'text', 'text': 'Posible duplicado; requiere confirmación adicional.'}]}},
                                    headers={'Cache-Control': 'no-store'})
            if not isinstance(saved, dict) or not saved.get('id'):
                raise RuntimeError('No se recibió confirmación de almacenamiento')
            result = {'content': [{'type': 'text', 'text':
                                   'Reporte registrado. Número oficial: ' + str(saved['id'])}],
                      'structuredContent': {'id': saved['id']}}
        except (HTTPException, ValueError) as exc:
            message = exc.detail if isinstance(exc, HTTPException) else str(exc)
            result = {'isError': True, 'content': [{'type': 'text', 'text': str(message)}]}
        except (PoolTimeout, TooManyRequests, psycopg.OperationalError,
                psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable):
            result = {'isError': True, 'content': [{'type': 'text', 'text':
                                                   'Servicio ocupado. Reintente con la misma clave de envío.'}]}
        return JSONResponse({'jsonrpc': '2.0', 'id': request_id, 'result': result},
                            headers={'Cache-Control': 'no-store'})
    else:
        return JSONResponse({
            'jsonrpc': '2.0', 'id': request_id,
            'error': {'code': -32601, 'message': 'Método no disponible'},
        }, headers={'Cache-Control': 'no-store'})
    return JSONResponse({'jsonrpc': '2.0', 'id': request_id, 'result': result},
                        headers={'Cache-Control': 'no-store'})


@app.get('/mcp')
async def mcp_transport_get():
    """MCP transport does not support unauthenticated streaming."""
    return Response(status_code=405, headers={'Allow': 'POST'})



@app.get('/.well-known/oauth-protected-resource')
@app.get('/.well-known/oauth-protected-resource/mcp')
async def mcp_oauth_resource_metadata():
    """RFC 9728 discovery, advertised only after an issuer is configured."""
    issuer = os.getenv('REPORTAPA_OAUTH_ISSUER', '').strip()
    if not issuer:
        raise HTTPException(503, 'OAuth todavía no configurado')
    parsed = urlparse(issuer)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise HTTPException(503, 'Configuración OAuth inválida')
    return JSONResponse(
        {
            'resource': 'https://reportapa.online/mcp',
            'authorization_servers': [issuer.rstrip('/')],
            'scopes_supported': ['reportapa:reports:create'],
            'bearer_methods_supported': ['header'],
        },
        headers={'Cache-Control': 'no-store'},
    )

