"""CareerRadar Pro API + responsive PWA; self-hosted MVP.
Business integrations without configured credentials are explicit disabled features.
"""
import os, re, json, math, io, secrets, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from urllib.parse import urlparse
from typing import Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .db import connect, init_db, ROOT
from .security import now, make_id, password_hash, verify_password, token_digest, create_session, current_user, admin_user
from .sources import fetch_jobs,clean_html,clean_https

log=logging.getLogger('careerradar')
@asynccontextmanager
async def lifespan(app):
    init_db()
    UPLOAD.mkdir(parents=True,exist_ok=True)
    yield

app=FastAPI(title='CareerRadar Pro',version='0.4.0',docs_url='/api/docs',openapi_url='/api/openapi.json',lifespan=lifespan)
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','').split(',') if x.strip()]
if origins: app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])
WEB=ROOT/'web';UPLOAD=ROOT/'var'/'uploads'
app.mount('/assets',StaticFiles(directory=WEB/'assets'),name='assets')

class Credentials(BaseModel):
    email: str = Field(min_length=5,max_length=254)
    password: str = Field(min_length=10,max_length=128)

class Profile(BaseModel):
    full_name: str = Field('',max_length=120)
    headline: str = Field('',max_length=180)
    country: str = Field('United Arab Emirates',max_length=100)
    city: str = Field('Dubai',max_length=100)
    desired_titles: str = Field('',max_length=300)
    skills: str = Field('',max_length=1000)
    years_experience: int = Field(0,ge=0,le=65)
    salary_min: int | None = Field(None,ge=0,le=100000000)
    salary_currency: str = Field('AED',pattern='^[A-Z]{3}$')
    summary: str = Field('',max_length=3500)

class AlertIn(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    query: str = Field('',max_length=160)
    location: str = Field('',max_length=160)
    frequency: Literal['immediate','2h','6h','daily','weekly','off']='daily'
    enabled: bool=True

class ApplicationIn(BaseModel):
    job_id: str | None=None
    company: str=Field(min_length=1,max_length=180)
    title: str=Field(min_length=1,max_length=180)
    status: Literal['interested','applied','assessment','interview','followup','offer','rejected','withdrawn']='interested'
    applied_at: str | None=Field(None,max_length=32)
    follow_up_at: str | None=Field(None,max_length=32)
    notes: str=Field('',max_length=4000)

class SourceIn(BaseModel):
    kind: Literal['greenhouse','lever']
    slug: str=Field(pattern='^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
    display_name: str=Field(min_length=1,max_length=120)

class JobIn(BaseModel):
    company: str=Field(min_length=1,max_length=180)
    title: str=Field(min_length=1,max_length=250)
    location: str=Field('',max_length=250)
    country: str=Field('',max_length=100)
    description: str=Field('',max_length=30000)
    url: str=Field(max_length=2000)

class ReportIn(BaseModel):
    reason: str=Field(min_length=8,max_length=1500)

# API response utilities

def rows(sql,args=()):
    with connect() as c: return [dict(x) for x in c.execute(sql,args).fetchall()]

def one(sql,args=()):
    with connect() as c:
        r=c.execute(sql,args).fetchone()
        return dict(r) if r else None

def err(code,msg): raise HTTPException(status_code=code,detail=msg)

# Low-cost local request throttle; use gateway/Redis across replicas in production.
_throttle=defaultdict(deque)
def throttle(request:Request,key:str,limit=10,seconds=60):
    ip=(request.client.host if request.client else 'local')
    bucket=_throttle[(ip,key)];tick=datetime.now(timezone.utc).timestamp()
    while bucket and tick-bucket[0]>seconds:bucket.popleft()
    if len(bucket)>=limit:err(429,'Too many requests. Try again later.')
    bucket.append(tick)

@app.get('/api/health')
def health():return {'status':'ok','app':'CareerRadar Pro','version':'0.4.0'}

@app.post('/api/auth/register')
def register(data:Credentials,request:Request):
    throttle(request,'register',5,3600)
    email=data.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):err(422,'Enter a valid email address')
    uid=make_id();stamp=now()
    role='seeker'  # Admin promotion is an explicit server-side operator action only.
    with connect() as c:
        if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():err(409,'Account already exists')
        c.execute('INSERT INTO users(id,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(uid,email,password_hash(data.password),role,stamp))
        c.execute('INSERT INTO profiles(user_id,updated_at) VALUES(?,?)',(uid,stamp))
        token=create_session(c,uid)
    return {'token':token,'user':{'id':uid,'email':email,'role':role}}

@app.post('/api/auth/login')
def login(data:Credentials,request:Request):
    throttle(request,'login',10,600)
    email=data.email.strip().lower()
    with connect() as c:
        u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not u or u['disabled'] or not verify_password(data.password,u['password_hash']):err(401,'Invalid email or password')
        token=create_session(c,u['id'])
        return {'token':token,'user':{'id':u['id'],'email':email,'role':u['role']}}

@app.get('/api/auth/me')
def whoami(user=Depends(current_user)): return user

@app.post('/api/auth/logout')
def logout(request:Request,user=Depends(current_user)):
    tok=request.headers.get('authorization','')[7:]
    with connect() as c:c.execute('DELETE FROM sessions WHERE token_hash=? AND user_id=?',(token_digest(tok),user['id']))
    return {'ok':True}

@app.delete('/api/auth/account')
def delete_account(user=Depends(current_user)):
    with connect() as c:
        files=[x['stored_name'] for x in c.execute('SELECT stored_name FROM cv_documents WHERE user_id=?',(user['id'],))]
        c.execute('DELETE FROM users WHERE id=?',(user['id'],))
    for filename in files:
        (UPLOAD/filename).unlink(missing_ok=True)
    return {'deleted':True,'notice':'Account data removed from active database; backups follow configured retention.'}

@app.get('/api/profile')
def get_profile(user=Depends(current_user)):
    profile=one('SELECT * FROM profiles WHERE user_id=?',(user['id'],))
    return profile or {}

@app.put('/api/profile')
def update_profile(data:Profile,user=Depends(current_user)):
    values=data.model_dump()
    with connect() as c:
        c.execute('''UPDATE profiles SET full_name=?, headline=?, country=?, city=?, desired_titles=?,skills=?,years_experience=?,salary_min=?,salary_currency=?,summary=?,updated_at=? WHERE user_id=?''',
                  (*values.values(),now(),user['id']))
    return get_profile(user)

@app.get('/api/jobs')
def search_jobs(q:str='',location:str='',source:str='',sort:Literal['recent','company','title']='recent',page:int=1,page_size:int=20):
    page=max(1,min(page,10000));page_size=max(1,min(page_size,50))
    where=["status='active'"];params=[]
    if q.strip():
        term='%'+q.strip()[:120].replace('%','\\%').replace('_','\\_')+'%'
        where.append("(title LIKE ? ESCAPE '\\' OR company LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        params += [term]*3
    if location.strip():
        where.append("(location LIKE ? OR country LIKE ?)")
        params += ['%'+location.strip()[:100]+'%']*2
    if source.strip():where.append('source=?');params.append(source[:150])
    where_sql=' AND '.join(where)
    orders={'recent':'COALESCE(posted_at, first_seen_at) DESC, id DESC','company':'company COLLATE NOCASE ASC,id DESC','title':'title COLLATE NOCASE ASC,id DESC'}
    total=one('SELECT count(*) AS n FROM jobs WHERE '+where_sql,params)['n']
    jobs=rows(f'SELECT id,source,company,title,location,country,work_type,description,url,posted_at,first_seen_at,salary_min,salary_max,currency FROM jobs WHERE {where_sql} ORDER BY {orders[sort]} LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size])
    for j in jobs:j['description']=j['description'][:450]
    return {'items':jobs,'total':total,'page':page,'pages':math.ceil(total/page_size),'page_size':page_size}

@app.get('/api/jobs/{job_id}')
def get_job(job_id:str):
    job=one("SELECT * FROM jobs WHERE id=? AND status='active'",(job_id,))
    if not job:err(404,'Job not found or expired')
    return job

@app.post('/api/jobs/{job_id}/report')
def report_job(job_id:str,data:ReportIn,user=Depends(current_user)):
    if not one('SELECT id FROM jobs WHERE id=?',(job_id,)):err(404,'Job not found')
    with connect() as c:c.execute('INSERT INTO job_reports VALUES(?,?,?,?,?)',(make_id(),user['id'],job_id,data.reason,now()))
    return {'ok':True,'message':'Report submitted for review'}

@app.get('/api/saved')
def saved(user=Depends(current_user)):
    return rows('''SELECT j.id,j.title,j.company,j.location,j.url,j.first_seen_at,j.source FROM saves s JOIN jobs j ON s.job_id=j.id WHERE s.user_id=? ORDER BY s.created_at DESC''',(user['id'],))

@app.post('/api/saved/{job_id}')
def save_job(job_id:str,user=Depends(current_user)):
    if not one('SELECT id FROM jobs WHERE id=?',(job_id,)):err(404,'Job not found')
    with connect() as c:c.execute('INSERT OR IGNORE INTO saves VALUES(?,?,?)',(user['id'],job_id,now()))
    return {'ok':True}

@app.delete('/api/saved/{job_id}')
def unsave_job(job_id:str,user=Depends(current_user)):
    with connect() as c:c.execute('DELETE FROM saves WHERE user_id=? AND job_id=?',(user['id'],job_id))
    return {'ok':True}

@app.get('/api/alerts')
def list_alerts(user=Depends(current_user)):
    return rows('SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC',(user['id'],))

@app.post('/api/alerts')
def create_alert(data:AlertIn,user=Depends(current_user)):
    aid=make_id()
    with connect() as c:c.execute('INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?)',(aid,user['id'],data.name,data.query,data.location,data.frequency,int(data.enabled),now()))
    return {'id':aid,'ok':True}

@app.delete('/api/alerts/{alert_id}')
def delete_alert(alert_id:str,user=Depends(current_user)):
    with connect() as c:c.execute('DELETE FROM alerts WHERE id=? AND user_id=?',(alert_id,user['id']))
    return {'ok':True}

@app.get('/api/notifications')
def notifications(user=Depends(current_user)):
    return rows('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(user['id'],))

@app.post('/api/notifications/{nid}/read')
def read_notification(nid:str,user=Depends(current_user)):
    with connect() as c:c.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?',(now(),nid,user['id']))
    return {'ok':True}

@app.get('/api/applications')
def applications(user=Depends(current_user)):
    return rows('SELECT * FROM applications WHERE user_id=? ORDER BY updated_at DESC',(user['id'],))

@app.post('/api/applications')
def create_application(data:ApplicationIn,user=Depends(current_user)):
    aid=make_id();d=data.model_dump()
    if d['job_id'] and not one('SELECT id FROM jobs WHERE id=?',(d['job_id'],)):
        err(404,'Job not found')
    with connect() as c:
        c.execute('''INSERT INTO applications(id,user_id,job_id,company,title,status,applied_at,follow_up_at,notes,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(aid,user['id'],d['job_id'],d['company'],d['title'],d['status'],d['applied_at'],d['follow_up_at'],d['notes'],now(),now()))
    return {'id':aid,'ok':True}

@app.put('/api/applications/{aid}')
def update_application(aid:str,data:ApplicationIn,user=Depends(current_user)):
    d=data.model_dump()
    with connect() as c:
        result=c.execute('''UPDATE applications SET job_id=?,company=?,title=?,status=?,applied_at=?,follow_up_at=?,notes=?,updated_at=? WHERE id=? AND user_id=?''',
                  (d['job_id'],d['company'],d['title'],d['status'],d['applied_at'],d['follow_up_at'],d['notes'],now(),aid,user['id']))
        if not result.rowcount:err(404,'Application not found')
    return {'ok':True}

@app.delete('/api/applications/{aid}')
def delete_application(aid:str,user=Depends(current_user)):
    with connect() as c:c.execute('DELETE FROM applications WHERE id=? AND user_id=?',(aid,user['id']))
    return {'ok':True}

@app.get('/api/applications/export.csv')
def export_applications(user=Depends(current_user)):
    import csv
    output=io.StringIO();writer=csv.writer(output)
    keys=['company','title','status','applied_at','follow_up_at','notes']
    writer.writerow(keys)
    def safe_csv(value):
        value=str(value or '')
        return '\''+value if value.lstrip().startswith(('=','+','-','@')) else value
    for r in applications(user):writer.writerow([safe_csv(r.get(k)) for k in keys])
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="applications.csv"'})

@app.get('/api/match/{job_id}')
def match_job(job_id:str,user=Depends(current_user)):
    profile=get_profile(user);job=get_job(job_id)
    text=(job['title']+' '+job['description']).lower()
    titles=[x.strip().lower() for x in re.split(r'[,;\n]+',profile.get('desired_titles') or '') if x.strip()]
    skills=[x.strip().lower() for x in re.split(r'[,;\n]+',profile.get('skills') or '') if x.strip()]
    matched=[s for s in skills if s in text]
    missing=[] # Cannot reliably infer absent requirements without structured extraction.
    title_hit=any(t in job['title'].lower() or job['title'].lower() in t for t in titles)
    loc=profile.get('city','').lower() in (job.get('location') or '').lower() if profile.get('city') else False
    score=round(25*int(title_hit)+45*(len(matched)/len(skills) if skills else 0)+20*int(loc)+10*int(bool(profile.get('summary'))))
    return {'score':score,'type':'heuristic relevance (not hiring probability)',
            'skills_matched':matched,'missing':'Unknown without structured requirements',
            'title_match':title_hit,'location_match':loc,
            'explanation':'This rule-based estimate compares declared titles, skills and preferred city. It cannot predict an employer decision.'}

@app.post('/api/cv/upload')
async def upload_cv(file:UploadFile=File(...),user=Depends(current_user)):
    allowed={'.pdf','.docx','.txt'}
    ext=Path(file.filename or '').suffix.lower()
    if ext not in allowed:err(415,'Supported file types: PDF, DOCX, TXT')
    payload=await file.read(3_000_001)
    if len(payload)>3_000_000:err(413,'Maximum file size 3 MB')
    if ext=='.pdf' and not payload.startswith(b'%PDF-'):err(415,'Invalid PDF')
    if ext=='.docx' and not payload.startswith(b'PK'):err(415,'Invalid DOCX')
    try:
        if ext=='.pdf':
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(payload),strict=True)
            extracted='\n'.join(page.extract_text() or '' for page in reader.pages[:30])
        elif ext=='.docx':
            from docx import Document
            document=Document(io.BytesIO(payload))
            extracted='\n'.join(p.text for p in document.paragraphs)
        else:extracted=payload.decode('utf-8')
    except Exception:err(422,'Could not read this document')
    cid=make_id();filename=cid+ext
    UPLOAD.mkdir(parents=True,exist_ok=True)
    (UPLOAD/filename).write_bytes(payload)
    with connect() as c:c.execute('INSERT INTO cv_documents VALUES(?,?,?,?,?,?,?)',
      (cid,user['id'],Path(file.filename or 'resume').name[:180],filename,len(payload),extracted[:60000],now()))
    return {'id':cid,'filename':file.filename,'characters_extracted':len(extracted),'note':'CV uploaded privately. Extracted text is not sent to an AI provider.'}

@app.get('/api/cv')
def cv_list(user=Depends(current_user)):
    return rows('SELECT id,filename,bytes,created_at FROM cv_documents WHERE user_id=? ORDER BY created_at DESC',(user['id'],))

@app.get('/api/cv/{cid}/download')
def cv_download(cid:str,user=Depends(current_user)):
    doc=one('SELECT * FROM cv_documents WHERE id=? AND user_id=?',(cid,user['id']))
    if not doc:err(404,'Document not found')
    path=UPLOAD/doc['stored_name']
    if not path.is_file():err(404,'Document bytes missing')
    return FileResponse(path,filename=doc['filename'],media_type='application/octet-stream')

@app.delete('/api/cv/{cid}')
def cv_delete(cid:str,user=Depends(current_user)):
    with connect() as c:
        doc=c.execute('SELECT * FROM cv_documents WHERE id=? AND user_id=?',(cid,user['id'])).fetchone()
        if not doc:err(404,'Document not found')
        c.execute('DELETE FROM cv_documents WHERE id=? AND user_id=?',(cid,user['id']))
    (UPLOAD/doc['stored_name']).unlink(missing_ok=True)
    return {'ok':True}

@app.get('/api/cv/resume/generate.pdf')
def generate_resume(user=Depends(current_user)):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    prof=get_profile(user);buffer=io.BytesIO();page=canvas.Canvas(buffer,pagesize=A4)
    page.setTitle('CareerRadar Resume')
    y=800
    def line(s,size=11,spacing=18):
        nonlocal y
        page.setFont('Helvetica',size)
        for segment in [s[i:i+100] for i in range(0,len(s),100)]:
            page.drawString(46,y,segment);y-=spacing
            if y<65:page.showPage();y=800
    line(prof.get('full_name') or 'Your Name',20,28)
    line(prof.get('headline') or 'Professional Profile',13,24)
    line((prof.get('city') or '')+', '+(prof.get('country') or ''),10,30)
    line('Professional Summary',14,24)
    line(prof.get('summary') or 'Add your professional summary in Profile.',10)
    y-=18;line('Skills',14,24)
    line(prof.get('skills') or 'Add skills in Profile.',10)
    page.save();buffer.seek(0)
    return StreamingResponse(buffer,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="careerradar-resume.pdf"'})

@app.get('/api/admin/overview')
def admin_overview(user=Depends(admin_user)):
    counts={}
    with connect() as c:
        for table in ('users','jobs','alerts','applications','providers','job_reports'):
            counts[table]=c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
    return {'counts':counts,'providers':rows('SELECT * FROM providers ORDER BY display_name'),
            'runs':rows('SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT 20'),
            'reports':rows('SELECT * FROM job_reports ORDER BY created_at DESC LIMIT 20')}

@app.post('/api/admin/providers')
def add_provider(data:SourceIn,user=Depends(admin_user)):
    provider_id=data.kind+':'+data.slug.lower()
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO providers(id,kind,slug,display_name,created_at) VALUES(?,?,?,?,?)',(provider_id,data.kind,data.slug,data.display_name,now()))
        c.execute('INSERT INTO audit_log VALUES(?,?,?,?,?)',(make_id(),user['id'],'provider-added',provider_id,now()))
    return {'id':provider_id,'ok':True,'warning':'Confirm commercial republication rights for this source before public deployment.'}

@app.post('/api/admin/jobs')
def post_job(data:JobIn,user=Depends(admin_user)):
    try:url=clean_https(data.url)
    except ValueError:err(422,'Apply link must use HTTPS')
    source='direct:admin';job_id=make_id()
    with connect() as c:c.execute('''INSERT INTO jobs(id,source,external_id,company,title,location,country,description,url,first_seen_at,last_seen_at,status)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(job_id,source,job_id,data.company,data.title,data.location,data.country,clean_html(data.description),url,now(),now(),'active'))
    return {'id':job_id,'ok':True}

@app.post('/api/admin/sync/{provider_id:path}')
async def sync_provider(provider_id:str,user=Depends(admin_user)):
    p=one('SELECT * FROM providers WHERE id=? AND enabled=1',(provider_id,))
    if not p:err(404,'Provider not configured')
    return await run_sync(p)

async def run_sync(p):
    run=make_id();stamp=now()
    with connect() as c:c.execute('INSERT INTO ingestion_runs(id,provider_id,started_at,status) VALUES(?,?,?,?)',(run,p['id'],stamp,'running'))
    try:
        jobs=await fetch_jobs(p['kind'],p['slug'])
        fresh=updated=0
        with connect() as c:
            for item in jobs:
                previous=c.execute('SELECT id FROM jobs WHERE id=?',(item['id'],)).fetchone()
                if previous:
                    c.execute('''UPDATE jobs SET company=?,title=?,location=?,description=?,url=?,posted_at=?,last_seen_at=?,status='active' WHERE id=?''',
                              (item['company'],item['title'],item['location'],item['description'],item['url'],item['posted_at'],now(),item['id']))
                    updated+=1
                else:
                    c.execute('''INSERT INTO jobs(id,source,external_id,company,title,location,country,work_type,description,url,posted_at,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (item['id'],item['source'],item['external_id'],item['company'],item['title'],item['location'],item['country'],item['work_type'],item['description'],item['url'],item['posted_at'],now(),now()))
                    fresh+=1
            c.execute('UPDATE ingestion_runs SET finished_at=?,status=?,new_count=?,updated_count=? WHERE id=?',(now(),'complete',fresh,updated,run))
        return {'ok':True,'new':fresh,'updated':updated,'provider':p['id']}
    except Exception as exc:
        # Do not expose internal tracebacks to users.
        log.exception('Job provider synchronization failed: %s',p['id'])
        with connect() as c:c.execute('UPDATE ingestion_runs SET finished_at=?,status=?,error=? WHERE id=?',(now(),'failed',str(exc)[:300],run))
        err(502,'Job provider request failed. Check admin ingestion log.')

@app.get('/api/admin/export.json')
def admin_export(user=Depends(admin_user)):
    # No user PII in admin snapshot; individual user exports would require a separate consent flow.
    return {'jobs':rows('SELECT * FROM jobs'),'providers':rows('SELECT * FROM providers')}

@app.get('/api/account/export')
def account_export(user=Depends(current_user)):
    return {'user':user,'profile':get_profile(user),
            'saved':saved(user),'alerts':list_alerts(user),
            'applications':applications(user),'cv_metadata':cv_list(user),
            'cv_shares':__import__('server.extra',fromlist=['list_shares']).list_shares(user),
            'tailored_documents':__import__('server.tailoring',fromlist=['list_drafts']).list_drafts(user)}

@app.get('/api/features')
def features():
    return {'live_data_sources':'configurable','ai_assistant':False,'ai_cv_tailoring':bool(os.getenv('OPENAI_API_KEY')),'source_grounded_cv_cover_letter':True,
            'subscriptions':False,'email_push':False,'in_app_alerts':True,
            'trust_radar':'provenance_and_freshness_only','manual_email_review':True,
            'walkin_radar':True,'application_kit':'deterministic_draft','whatsapp_share':True,
            'job_comparison':True,'directions_links':True,'mohre_guidance':True,
            'skills_roadmap':'rule_based','recruitment_activity':'source_timestamps_only',
            'revocable_cv_shares':True,'weekly_report':True,
            'email_oauth':False,'whatsapp_auto_alerts':False,'commute_time_filter':False,
            'message':'Requires external provider integrations for automatic mail, WhatsApp and commute estimates.'}

from .extra import router as extra_router
from .tailoring import router as tailoring_router
app.include_router(extra_router)
app.include_router(tailoring_router)

@app.get('/api/legal/{name}')
def legal(name:str):
    if name not in ('privacy','terms'):err(404,'Document not found')
    return {'status':'draft','document':name,'note':'Legal templates must be reviewed by qualified counsel prior to commercial release.'}

@app.get('/manifest.webmanifest')
def manifest():return FileResponse(WEB/'manifest.webmanifest',media_type='application/manifest+json')

@app.get('/service-worker.js')
def service_worker():return FileResponse(WEB/'service-worker.js',media_type='text/javascript')

@app.get('/')
def index():return FileResponse(WEB/'index.html')

@app.get('/{path:path}')
def spa(path:str):
    if path.startswith('api/'):err(404,'API route not found')
    return FileResponse(WEB/'index.html')
