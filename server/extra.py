"""CareerRadar 0.3: trust, comparison, interview radar, communication assistance,
share links and analytics. External services are never implied to be active.
"""
from __future__ import annotations
import hashlib, re, secrets, urllib.parse, json, io
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
from .db import connect, ROOT
from .security import now, make_id, current_user, admin_user
from .sources import clean_https

router=APIRouter(prefix='/api')
UPLOAD=ROOT/'var'/'uploads'
def fail(status, message):raise HTTPException(status_code=status, detail=message)
def take(sql, args=()):
    with connect() as c:return [dict(r) for r in c.execute(sql,args)]
def first(sql,args=()):
    with connect() as c:
        r=c.execute(sql,args).fetchone();return dict(r) if r else None

def get_live_job(jid):
    j=first("SELECT * FROM jobs WHERE id=? AND status='active'",(jid,))
    if not j:fail(404,'Active vacancy not found')
    return j

def trust_fields(job):
    # Last seen denotes ingestion or administrator action, NOT an independent employer check.
    last=job.get('last_seen_at')
    dt=None
    if last:
        try:dt=datetime.fromisoformat(last.replace('Z','+00:00'))
        except ValueError:pass
    age=(datetime.now(timezone.utc)-dt).total_seconds()/3600 if dt else None
    src=job.get('source','')
    kind='Provider feed' if src.startswith(('greenhouse:','lever:')) else 'Administrator-entered listing' if src=='direct:admin' else 'Other source'
    return {'source_type':kind,'source':src,'original_url':job['url'],
      'first_seen_at':job['first_seen_at'],'last_seen_at':last,
      'posted_at':job['posted_at'],'freshness':('not_checked' if age is None else 'recently_seen' if age<48 else 'older_than_48_hours' if age<168 else 'stale'),
      'employer_identity_verified':False,'application_link_verified':False,
      'notice':'Listing was ingested or entered on this date. Employer identity and application availability have NOT been independently verified.'}

@router.get('/jobs/{job_id}/trust')
def job_trust(job_id:str):return trust_fields(get_live_job(job_id))

@router.get('/jobs/{job_id}/activity')
def job_activity(job_id:str):
    j=get_live_job(job_id)
    return {'company':j['company'],'first_discovered':j['first_seen_at'],
       'last_seen_in_source_or_admin':j['last_seen_at'],'employer_response_rate':None,
       'applications_received':None,'hiring_activity_verified':False,
       'notice':'Recruiter activity or response rates are unavailable: no authorized employer data connection.'}

@router.get('/jobs/compare/batch')
def job_compare(ids:str=Query('',max_length=1000)):
    chosen=[x.strip() for x in ids.split(',') if x.strip()]
    if not (2<=len(chosen)<=4) or len(set(chosen))!=len(chosen):fail(422,'Choose 2 to 4 different vacancies')
    jobs=[get_live_job(x) for x in chosen]
    return {'items':[{**{k:j.get(k) for k in ('id','title','company','location','country','work_type','salary_min','salary_max','currency','posted_at','first_seen_at','url')},'trust':trust_fields(j)} for j in jobs],
      'note':'Unknown salary, benefits and conditions are not estimated.'}

class Event(BaseModel):
    company:str=Field(min_length=2,max_length=180)
    title:str=Field(min_length=3,max_length=180)
    venue:str=Field(min_length=3,max_length=250)
    city:str=Field(min_length=2,max_length=100)
    country:str=Field('United Arab Emirates',max_length=100)
    starts_at:datetime
    ends_at:datetime
    source_url:str=Field(max_length=2000)
    requirements:str=Field('',max_length=2000)
    documents:str=Field('',max_length=1000)
    moderator_reviewed:bool=False

@router.get('/walkins')
def walkin_events(city:str='',limit:int=30):
    limit=max(1,min(limit,100))
    sql="SELECT id,company,title,venue,city,country,starts_at,ends_at,source_url,requirements,documents,created_at,reviewed_at FROM walkin_events WHERE status='published' AND starts_at>=?"
    args=[now()]
    if city.strip():sql+=' AND city LIKE ?';args.append('%'+city.strip()[:100]+'%')
    sql+=' ORDER BY starts_at ASC LIMIT ?';args.append(limit)
    return {'items':take(sql,args),'note':'Events are moderator-reviewed against a supplied source, not guaranteed by the employer. Confirm with the original organizer before travelling.'}

@router.post('/admin/walkins')
def create_walkin(data:Event,user=Depends(admin_user)):
    if data.ends_at<=data.starts_at:fail(422,'End time must be later than start time')
    try:url=clean_https(data.source_url)
    except ValueError:fail(422,'Source must use HTTPS')
    eid=make_id();stamp=now(); reviewed=stamp if data.moderator_reviewed else None
    with connect() as c:
        c.execute('''INSERT INTO walkin_events (id,company,title,venue,city,country,starts_at,ends_at,source_url,requirements,documents,status,reviewed_at,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(eid,data.company,data.title,data.venue,data.city,data.country,
            data.starts_at.astimezone(timezone.utc).isoformat(),data.ends_at.astimezone(timezone.utc).isoformat(),url,data.requirements,data.documents,
            'published' if data.moderator_reviewed else 'pending',reviewed,stamp))
        c.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(make_id(),user['id'],'walkin-created',eid,stamp))
    return {'id':eid,'status':'published' if data.moderator_reviewed else 'pending'}

@router.get('/admin/walkins')
def admin_walkins(user=Depends(admin_user)):
    return take('SELECT * FROM walkin_events ORDER BY starts_at DESC LIMIT 100')

@router.post('/admin/walkins/{event_id}/publish')
def publish_walkin(event_id:str,user=Depends(admin_user)):
    with connect() as c:
        updated=c.execute("UPDATE walkin_events SET status='published',reviewed_at=? WHERE id=?",(now(),event_id))
        if not updated.rowcount:fail(404,'Event not found')
        c.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(make_id(),user['id'],'walkin-published',event_id,now()))
    return {'ok':True}

@router.get('/commute/directions')
def commute_directions(origin:str,job_id:str,mode:Literal['driving','transit','walking']='driving'):
    j=get_live_job(job_id)
    if not origin.strip() or len(origin)>160:fail(422,'Enter a valid starting location')
    destination=', '.join(p for p in [j['location'],j['country']] if p)
    if not destination:fail(422,'Job location is unknown')
    params=urllib.parse.urlencode({'api':'1','origin':origin.strip(),'destination':destination,'travelmode':mode})
    return {'url':'https://www.google.com/maps/dir/?'+params,'estimated_minutes':None,
        'note':'Opens Google Maps to calculate a real route. CareerRadar has no live travel-time integration and cannot filter by commute time yet.'}

class MailPreview(BaseModel):
    sender:str=Field('',max_length=250)
    subject:str=Field('',max_length=300)
    body:str=Field('',max_length=8000)

def classify_mail(subject,body):
    text=(subject+'\n'+body).lower()
    # Explicit phrase classes are deliberately conservative to avoid erroneous record changes.
    if re.search(r'\b(unfortunately|not selected|not moving forward|unsuccessful application|regret to inform)\b',text):return 'rejected'
    if re.search(r'\b(offer letter|pleased to offer|job offer|employment offer)\b',text):return 'offer'
    if re.search(r'\b(interview invitation|invite you to an interview|schedule an interview|interview scheduled)\b',text):return 'interview'
    if re.search(r'\b(application received|thank you for applying|application confirmation|received your application)\b',text):return 'applied'
    return 'unknown'

@router.post('/email/preview')
def mail_preview(data:MailPreview,user=Depends(current_user)):
    suggestion=classify_mail(data.subject,data.body)
    return {'suggested_status':suggestion,'requires_confirmation':True,'source':'manually pasted email',
      'warning':'This is a keyword-based classification, not a confirmed recruiter status. The pasted email is not stored or sent to a provider.'}

class ConfirmMail(MailPreview):
    application_id:str
    status:Literal['applied','interview','offer','rejected','assessment','followup']

@router.post('/email/confirm')
def confirm_mail(data:ConfirmMail,user=Depends(current_user)):
    candidate=classify_mail(data.subject,data.body)
    if data.status!=candidate and candidate=='unknown':fail(422,'Email did not contain a recognizable application status; change the application manually instead')
    with connect() as c:
        r=c.execute('UPDATE applications SET status=?,updated_at=? WHERE id=? AND user_id=?',(data.status,now(),data.application_id,user['id']))
        if not r.rowcount:fail(404,'Application not found')
    return {'updated':True,'status':data.status,'method':'user-confirmed manual email classification'}

@router.get('/jobs/{job_id}/application-kit')
def application_kit(job_id:str,user=Depends(current_user)):
    j=get_live_job(job_id)
    p=first('SELECT * FROM profiles WHERE user_id=?',(user['id'],))
    if not p:fail(404,'Complete your profile first')
    existing=[x.strip() for x in re.split('[,;\n]+',p['skills'] or '') if x.strip()]
    matched=[s for s in existing if s.lower() in (j['title']+' '+j['description']).lower()]
    name=p['full_name'] or '[Your full name]'
    intro=(p['headline'] or 'professional')
    letter=f"Dear Hiring Team,\n\nI am writing to express my interest in the {j['title']} role at {j['company']}. "
    letter+=f"My professional profile focuses on {intro}. "
    if matched:letter+='My relevant skills include '+', '.join(matched[:6])+'. '
    letter+='I would welcome the opportunity to discuss how my experience aligns with the role.\n\nKind regards,\n'+name
    return {'job_id':job_id,'company':j['company'],'title':j['title'],
      'matching_declared_skills':matched,'cover_letter_draft':letter,
      'cv_editing_notes':['Only include qualifications you genuinely have.','Use examples of relevant work from your actual experience.','Check the employer requirements against your CV before applying.'],
      'submission':'manual-review-required','notice':'Draft assembled from your profile and source vacancy. No application was sent and no qualifications were fabricated.'}

@router.get('/jobs/{job_id}/roadmap')
def skills_roadmap(job_id:str,user=Depends(current_user)):
    j=get_live_job(job_id);p=first('SELECT * FROM profiles WHERE user_id=?',(user['id'],))
    known={x.strip().lower() for x in re.split('[,;\n]+',p['skills'] or '') if x.strip()} if p else set()
    # Surface explicitly mentioned software, not inferred requirements.
    options=['Primavera P6','Power BI','Excel','AutoCAD','Revit','Python','SQL','BIM','AWS','JavaScript','Project management','Scheduling','Construction safety','Cost control','English','Arabic']
    req=[s for s in options if s.lower() in j['description'].lower() or s.lower() in j['title'].lower()]
    missing=[s for s in req if s.lower() not in known]
    steps=[{'skill':s,'next_step':f'Find official documentation or an accredited course for {s}; build a real example demonstrating your proficiency.',
            'status':'suggestion_not_verified_requirement'} for s in missing]
    return {'job_id':job_id,'explicitly_mentioned_terms':req,'not_in_declared_profile':missing,'steps':steps,
      'notice':'Rule-based suggestions, not a complete parsing of employer requirements or recommendations of verified courses.'}

class OfferText(BaseModel):
    text:str=Field(min_length=10,max_length=15000)

@router.post('/offers/check')
def offer_check(data:OfferText,user=Depends(current_user)):
    value=data.text.lower();flags=[]
    for pattern,reason in [(r'(processing|registration|recruitment|visa|offer) fees?', 'Requests for recruitment or processing fees'),
       (r'\b(payment|deposit|transfer)\b.{0,80}\b(before|first|advance|upfront)\b','Advance payment requests'),
       (r'(send|share).{0,60}(otp|password|bank pin)','Requests for private access codes')]:
        if re.search(pattern,value):flags.append(reason)
    return {'warning_signs':flags,'verified':False,'official_portal':'https://www.mohre.gov.ae/',
      'note':'This is a simple text warning check, NOT validation of an offer or employer. Verify through MOHRE official channels and never pay unexpected recruitment fees.'}

@router.get('/integrations/status')
def integration_status():
    return {'inbox_oauth':'not_connected','whatsapp_business_api':'not_connected','routing_api':'not_connected',
       'email_manual_review':'available','whatsapp_share_link':'available','map_directions_link':'available',
       'notes':'Background mailbox access, automatic WhatsApp alerts and commute-time filtering need provider accounts, consent and live integrations.'}

class WhatsAppPreview(BaseModel):
    job_id:str

@router.post('/integrations/whatsapp/preview')
def whatsapp_share(data:WhatsAppPreview,user=Depends(current_user)):
    j=get_live_job(data.job_id)
    text=f"CareerRadar job: {j['title']} at {j['company']} ({j['location']}). Original source: {j['url']}"
    return {'url':'https://api.whatsapp.com/send?'+urllib.parse.urlencode({'text':text}),
       'message':text,'automatic_delivery':False,'note':'User-initiated sharing only. No automated message was sent.'}

class ShareIn(BaseModel):
    cv_id:str
    expires_days:Literal[1,7,30]=7
    max_opens:int=Field(10,ge=1,le=100)

@router.post('/cv/shares')
def create_share(data:ShareIn,user=Depends(current_user)):
    doc=first('SELECT id FROM cv_documents WHERE id=? AND user_id=?',(data.cv_id,user['id']))
    if not doc:fail(404,'CV not found')
    token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest();sid=make_id()
    expire=(datetime.now(timezone.utc)+timedelta(days=data.expires_days)).isoformat()
    with connect() as c:
        c.execute('INSERT INTO cv_shares(id,user_id,cv_id,token_hash,expires_at,max_opens,created_at) VALUES (?,?,?,?,?,?,?)',
                (sid,user['id'],data.cv_id,digest,expire,data.max_opens,now()))
    return {'id':sid,'path':'/api/public/cv-share/'+token,'expires_at':expire,
       'warning':'Treat this link as a password: anyone who obtains it can open your CV until expiry, revocation or the view limit.'}

@router.get('/cv/shares')
def list_shares(user=Depends(current_user)):
    return take('''SELECT s.id,s.cv_id,d.filename,s.expires_at,s.max_opens,s.open_count,s.revoked_at,s.created_at
       FROM cv_shares s JOIN cv_documents d ON d.id=s.cv_id WHERE s.user_id=? ORDER BY s.created_at DESC''',(user['id'],))

@router.delete('/cv/shares/{share_id}')
def revoke_share(share_id:str,user=Depends(current_user)):
    with connect() as c:
        r=c.execute('UPDATE cv_shares SET revoked_at=? WHERE id=? AND user_id=? AND revoked_at IS NULL',(now(),share_id,user['id']))
        if not r.rowcount:fail(404,'Active share not found')
    return {'revoked':True}

@router.get('/public/cv-share/{token}')
def public_cv(token:str,request:Request):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,100}',token):fail(404,'Link not found')
    # Constant-size digest and unconditional opaque response prevent enumeration.
    digest=hashlib.sha256(token.encode()).hexdigest()
    with connect() as c:
        doc=c.execute('''SELECT s.id,s.open_count,s.max_opens,d.filename,d.stored_name FROM cv_shares s JOIN cv_documents d ON d.id=s.cv_id
          WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND s.open_count<s.max_opens''',(digest,now())).fetchone()
        if not doc:fail(404,'Link expired, revoked or unavailable')
        from .main import UPLOAD as ACTIVE_UPLOAD
        path=ACTIVE_UPLOAD/doc['stored_name']
        if not path.is_file():fail(404,'Document unavailable')
        r=c.execute('UPDATE cv_shares SET open_count=open_count+1 WHERE id=? AND open_count<max_opens AND revoked_at IS NULL',(doc['id'],))
        if not r.rowcount:fail(404,'Link access limit reached')
        filename=doc['filename']
    response=FileResponse(path,filename=filename,media_type='application/octet-stream')
    response.headers['Cache-Control']='no-store';response.headers['X-Robots-Tag']='noindex, nofollow, noarchive';response.headers['Referrer-Policy']='no-referrer'
    return response

@router.get('/reports/weekly')
def weekly_report(weeks:int=8,user=Depends(current_user)):
    weeks=max(1,min(weeks,26));start=(datetime.now(timezone.utc)-timedelta(days=7*weeks)).isoformat()
    applications=take('SELECT id,status,created_at,updated_at,follow_up_at FROM applications WHERE user_id=?',(user['id'],))
    notices=take('SELECT created_at FROM notifications WHERE user_id=? AND created_at>=?',(user['id'],start))
    saved=take('SELECT created_at FROM saves WHERE user_id=? AND created_at>=?',(user['id'],start))
    breakdown=[]
    for i in range(weeks-1,-1,-1):
        since=(datetime.now(timezone.utc)-timedelta(days=7*(i+1))).isoformat()
        until=(datetime.now(timezone.utc)-timedelta(days=7*i)).isoformat()
        breakdown.append({'week_start':since[:10],
          'applications_added':sum(since<=a['created_at']<until for a in applications),
          'jobs_saved':sum(since<=s['created_at']<until for s in saved),
          'alerts_received':sum(since<=n['created_at']<until for n in notices)})
    statuses={}
    for a in applications:statuses[a['status']]=statuses.get(a['status'],0)+1
    today=datetime.now(timezone.utc).date().isoformat()
    due=[{'id':a['id'],'follow_up_at':a['follow_up_at']} for a in applications if a['follow_up_at'] and a['follow_up_at'][:10]<=today and a['status'] not in ('rejected','withdrawn','offer')]
    return {'weeks':breakdown,'current_application_status_counts':statuses,'due_followups':due,
      'notice':'Based on records tracked in CareerRadar, not external platform application totals. Saved-job counts refer to currently saved jobs.'}
