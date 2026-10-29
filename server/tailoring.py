"""Job-specific, source-grounded CV and cover-letter drafts.

No third-party LLM is called. All claims are drawn verbatim from the user's
profile or uploaded CV; the user must review and edit before applying.
"""
from __future__ import annotations
import io, json, re
from datetime import datetime, timezone
from html import escape as html_escape
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from .db import connect
from .security import current_user, make_id, now

router = APIRouter(prefix='/api')

# Explicit vocabulary rather than hallucinating requirements from arbitrary text.
SKILL_TERMS = (
    'Primavera P6','Microsoft Project','MS Project','Power BI','Excel','AutoCAD','Revit',
    'BIM','MEP','HVAC','Fire Fighting','Fire Alarm','Quantity Surveying',
    'Project Planning','Scheduling','Cost Control','Earned Value','Delay Analysis',
    'Risk Management','Procurement','Quality Control','HSE','Python','JavaScript',
    'React','TypeScript','SQL','PostgreSQL','AWS','Azure','Docker','Kubernetes',
    'Customer Service','Sales','Operations','Accounting','SAP','ERP','Communication',
    'Leadership','Data Analysis','Project Management','Site Engineering','Construction',
    'Electrical','Mechanical','Civil','Document Control','Contract Management',
    'Stakeholder Management','Testing and Commissioning'
)

class TailorRequest(BaseModel):
    cv_id: str | None = Field(None, max_length=80)
    kind: Literal['both','cv','cover_letter'] = 'both'
    tone: Literal['professional','concise','formal'] = 'professional'
    mode: Literal['local','ai'] = 'local'
    allow_external_processing: bool = False

class EditDraft(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=15, max_length=40000)


def reject(status:int, message:str):
    raise HTTPException(status_code=status,detail=message)


def lookup_job(job_id:str):
    with connect() as c:
        row=c.execute("SELECT * FROM jobs WHERE id=? AND status='active'", (job_id,)).fetchone()
        if not row:reject(404,'Active job not found')
        return dict(row)


def profile_for(user_id:str):
    with connect() as c:
        row=c.execute('SELECT * FROM profiles WHERE user_id=?',(user_id,)).fetchone()
        return dict(row) if row else {}


def source_cv(cv_id:str | None, user_id:str):
    if not cv_id:return None
    with connect() as c:
        row=c.execute('SELECT id,filename,extracted_text FROM cv_documents WHERE id=? AND user_id=?',(cv_id,user_id)).fetchone()
        if not row:reject(404,'Selected CV not found in your account')
        return dict(row)


def matches(text:str, term:str)->bool:
    return bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text,re.IGNORECASE))


def find_match(job_text:str, candidate_text:str):
    required=[term for term in SKILL_TERMS if matches(job_text,term)]
    confirmed=[term for term in required if matches(candidate_text,term)]
    missing=[term for term in required if term not in confirmed]
    return required, confirmed, missing


def normalize_lines(text:str, limit:int=24000)->list[str]:
    # Preserve uploaded qualifications and employer history without generating facts.
    return [re.sub(r'\s+',' ',line).strip() for line in text[:limit].splitlines() if line.strip()][:300]


def draft_resume(job, profile, cv, confirmed, tone):
    name=(profile.get('full_name') or '').strip() or 'YOUR NAME — please update your profile'
    headline=(profile.get('headline') or '').strip()
    location=', '.join(x for x in (profile.get('city','').strip(),profile.get('country','').strip()) if x)
    candidate_text=(cv or {}).get('extracted_text','').strip()
    source_lines=normalize_lines(candidate_text)
    skill_line=', '.join(confirmed) if confirmed else '[Add relevant skills supported by your experience]'
    summary=(profile.get('summary') or '').strip()
    # Never claim role-specific experience purely because the job listing mentions it.
    first_lines=[name]
    if headline:first_lines.append(headline)
    if location:first_lines.append(location)
    first_lines += ['', f'TARGET ROLE: {job["title"]} — {job["company"]}', '', 'PROFESSIONAL SUMMARY']
    if summary:first_lines.append(summary)
    else:first_lines.append('[Write a factual professional summary before sending]')
    first_lines += ['', 'RELEVANT SKILLS',skill_line]
    if source_lines:
        first_lines += ['', 'EXPERIENCE, EDUCATION AND QUALIFICATIONS',*source_lines]
    else:
        first_lines += ['', 'ADDITIONAL BACKGROUND',
          '[Add your verified work history, education and achievements before sending]']
        if profile.get('skills'):first_lines += ['Declared skills: '+profile['skills']]
    return '\n'.join(first_lines)


def draft_letter(job,profile,cv,confirmed,tone):
    name=(profile.get('full_name') or '').strip() or '[Your Name]'
    job_title,company=job['title'],job['company']
    # No claims unsupported by the user-provided profile/CV.
    intro=f'I am writing to express my interest in the {job_title} position at {company}.'
    if tone=='concise':intro=f'I would like to apply for the {job_title} role at {company}.'
    if tone=='formal':intro=f'Please accept this letter as my application for the position of {job_title} at {company}.'
    paras=['Dear Hiring Manager,','',intro]
    headline=(profile.get('headline') or '').strip()
    if headline:paras += ['',f'My current professional profile describes me as: {headline}.']
    if confirmed:
        phr=', '.join(confirmed[:6])
        paras += ['',f'My listed skills include {phr}, which are relevant to the requirements of this position. I would welcome the opportunity to discuss my experience and contributions in more detail.']
    elif profile.get('summary'):
        paras += ['',f'My professional profile states: {profile["summary"].strip()[:450]}']
    else:
        paras += ['', 'I would welcome the opportunity to discuss how my background meets the responsibilities described in the vacancy.']
    if profile.get('summary') and confirmed:
        paras += ['',f'My professional background: {profile["summary"].strip()[:350]}']
    paras += ['',f'Thank you for considering my application to {company}. I would appreciate the opportunity to discuss the role and provide further details.','', 'Sincerely,',name]
    return '\n'.join(paras)


@router.post('/jobs/{job_id}/tailor')
async def generate(job_id:str, request:TailorRequest, user=Depends(current_user)):
    job=lookup_job(job_id)
    if len(job.get('description') or '') < 30:
        reject(422,'This job has insufficient description to customize documents. Review the original posting.')
    profile=profile_for(user['id'])
    cv=source_cv(request.cv_id,user['id'])
    src=(cv or {}).get('extracted_text','')
    declared='\n'.join(str(profile.get(k) or '') for k in ('headline','skills','summary','desired_titles'))
    if len((declared+src).strip()) < 25:
        reject(422,'Upload your existing CV or complete your professional profile first.')
    if cv and len(src.strip()) < 30 and len(declared.strip()) < 25:
        reject(422,'This CV contains no usable extracted text. Upload a text-based CV or update your profile.')
    required, confirmed, missing = find_match(job['description'], declared+'\n'+src)
    ai_result=None
    if request.mode=='ai':
        if not request.allow_external_processing:
            reject(422,'Consent required before sending your profile and CV to an external AI provider.')
        from .tailor_ai import create_ai_drafts
        try: ai_result=await create_ai_drafts(job,profile,cv,request.tone,confirmed,missing,SKILL_TERMS)
        except RuntimeError as exc: reject(503,str(exc))
    creations=[];timestamp=now()
    with connect() as c:
        for kind in (('cv','cover_letter') if request.kind=='both' else (request.kind,)):
            content=(ai_result[kind] if ai_result else (draft_resume(job,profile,cv,confirmed,request.tone) if kind=='cv' else draft_letter(job,profile,cv,confirmed,request.tone)))
            did=make_id();title=f'{"Tailored CV" if kind=="cv" else "Cover Letter"} — {job["title"]} | {job["company"]}'
            c.execute('''INSERT INTO tailored_documents
            (id,user_id,job_id,cv_id,kind,title,content,match_terms_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',(did,user['id'],job_id,cv['id'] if cv else None,kind,title,content,json.dumps(confirmed),timestamp,timestamp))
            creations.append({'id':did,'title':title,'kind':kind,'content':content,'created_at':timestamp})
    return {'documents':creations,'matched_skills':confirmed,'unconfirmed_job_terms':missing,
        'job_title':job['title'],'company':job['company'],'method':('opt-in external AI draft' if ai_result else 'private source-grounded deterministic tailoring'),
        'warning':'Review all text and add only true facts before submitting. No employer application has been sent.'}


@router.get('/tailored')
def list_drafts(user=Depends(current_user)):
    with connect() as c:
        return [dict(r) for r in c.execute('''SELECT d.id,d.title,d.kind,d.updated_at,d.created_at,d.job_id,
             d.cv_id,j.company,j.title AS job_title FROM tailored_documents d
             JOIN jobs j ON d.job_id=j.id WHERE d.user_id=? ORDER BY d.updated_at DESC''',(user['id'],))]


def owned(document_id:str,user_id:str):
    with connect() as c:
        row=c.execute('SELECT * FROM tailored_documents WHERE id=? AND user_id=?',(document_id,user_id)).fetchone()
    if not row:reject(404,'Document not found')
    return dict(row)


@router.get('/tailored/{document_id}')
def get_draft(document_id:str,user=Depends(current_user)):
    d=owned(document_id,user['id']);d['matched_skills']=json.loads(d.pop('match_terms_json'))
    return d


@router.put('/tailored/{document_id}')
def edit_draft(document_id:str,payload:EditDraft,user=Depends(current_user)):
    owned(document_id,user['id'])
    with connect() as c:
        c.execute('UPDATE tailored_documents SET title=?,content=?,updated_at=? WHERE id=? AND user_id=?',
                  (payload.title,payload.content,now(),document_id,user['id']))
    return get_draft(document_id,user)


@router.delete('/tailored/{document_id}')
def delete_draft(document_id:str,user=Depends(current_user)):
    with connect() as c:
        cur=c.execute('DELETE FROM tailored_documents WHERE id=? AND user_id=?',(document_id,user['id']))
        if cur.rowcount==0:reject(404,'Document not found')
    return {'deleted':True}


def make_pdf(title:str,content:str)->bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import simpleSplit
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,KeepTogether
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    family='Helvetica'
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if os.path.isfile(font_path):
        try:
            if 'CRDejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('CRDejaVu',font_path))
            family='CRDejaVu'
        except Exception:pass
    b=io.BytesIO();pdf=SimpleDocTemplate(b,pagesize=A4,leftMargin=52,rightMargin=52,topMargin=54,bottomMargin=54,
                 title=title,author='CareerRadar Pro')
    sty=ParagraphStyle('body',fontName=family,fontSize=9.5,leading=15,textColor=colors.HexColor('#24364d'),spaceAfter=7)
    header=ParagraphStyle('head',parent=sty,fontSize=14,leading=20,spaceAfter=13,textColor=colors.HexColor('#163a66'))
    lines=content.splitlines();blocks=[]
    for i,line in enumerate(lines):
        txt=line.strip()
        if not txt:
            blocks.append(Spacer(1,5));continue
        if len(txt)<=75 and (txt.isupper() or (i==0 and len(txt)<75)):
            blocks.append(Paragraph(html_escape(txt),header))
        else:
            blocks.append(Paragraph(html_escape(txt),sty))
    pdf.build(blocks)
    return b.getvalue()


def make_docx(title:str,content:str)->bytes:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    d=Document();sec=d.sections[0];sec.left_margin=sec.right_margin=Inches(.85)
    sec.top_margin=sec.bottom_margin=Inches(.75)
    normal=d.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10)
    normal.paragraph_format.space_after=Pt(6)
    for i,line in enumerate(content.splitlines()):
        txt=line.strip()
        if not txt:
            d.add_paragraph('');continue
        if len(txt)<=75 and (txt.isupper() or i==0):d.add_heading(txt,level=1 if i==0 else 2)
        else:d.add_paragraph(txt)
    b=io.BytesIO();d.save(b);return b.getvalue()


@router.get('/tailored/{document_id}/export.{format}')
def export_draft(document_id:str,format:Literal['pdf','docx'],user=Depends(current_user)):
    d=owned(document_id,user['id'])
    if format=='pdf':
        data=make_pdf(d['title'],d['content']);media='application/pdf'
    else:
        data=make_docx(d['title'],d['content']);media='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    name=f'careerradar-{d["kind"]}-{d["id"][:8]}.{format}'
    return StreamingResponse(io.BytesIO(data),media_type=media,headers={'Content-Disposition':f'attachment; filename="{name}"',
     'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
