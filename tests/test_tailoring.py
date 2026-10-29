"""Job-specific CV and cover letter integration/authorization tests."""
import io
import pytest
from docx import Document
from pypdf import PdfReader
from fastapi.testclient import TestClient
from server import db
from server.main import app, _throttle
from server.bootstrap_admin import promote

@pytest.fixture
def client(tmp_path,monkeypatch):
    _throttle.clear()
    monkeypatch.setattr(db,'DB_PATH',str(tmp_path/'tailoring.sqlite3'))
    monkeypatch.setattr('server.main.UPLOAD',tmp_path/'uploads')
    with TestClient(app) as c: yield c

def sign_up(client,email):
    r=client.post('/api/auth/register',json={'email':email,'password':'safe-password-12345'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def create_job(client,admin,description='We require Primavera P6 and Power BI reporting for MEP Planning Engineer duties.'):
    r=client.post('/api/admin/jobs',headers=admin,json={
      'company':'Example Engineering','title':'MEP Planning Engineer','description':description,
      'location':'Dubai','url':'https://example.com/approved-job-link'})
    assert r.status_code==200,r.text
    return r.json()['id']

def test_create_edit_export_and_private_access(client):
    alice=sign_up(client,'alice@example.com');bob=sign_up(client,'bob@example.com')
    promote('alice@example.com');jid=create_job(client,alice)
    client.put('/api/profile',headers=alice,json={'full_name':'Alice Smith','skills':'Primavera P6, MEP','summary':'Worked with electrical site teams coordinating site schedules.'})
    original=b'Alice Smith\nMEP planning coordinator\nWorked with Primavera P6 and MEP site schedules.\nEducation: Civil Engineering\n'
    up=client.post('/api/cv/upload',headers=alice,files={'file':('original.txt',original,'text/plain')})
    assert up.status_code==200,up.text
    cv_id=up.json()['id']
    r=client.post(f'/api/jobs/{jid}/tailor',headers=alice,json={'kind':'both','tone':'professional','cv_id':cv_id})
    assert r.status_code==200,r.text
    data=r.json();assert len(data['documents'])==2
    assert 'Primavera P6' in data['matched_skills']
    assert 'Power BI' in data['unconfirmed_job_terms']
    cv,letter=data['documents']
    assert 'Education: Civil Engineering' in cv['content']
    assert 'Power BI' not in cv['content'] or 'Power BI' in ' '.join(data['unconfirmed_job_terms']) # no false qualifications
    assert 'Primavera P6' in letter['content']
    assert 'Power BI' not in letter['content']
    assert 'Example Engineering' in letter['content']
    assert len(client.get('/api/tailored',headers=alice).json())==2
    assert client.get('/api/tailored',headers=bob).json()==[]
    assert client.get('/api/tailored/'+cv['id'],headers=bob).status_code==404
    assert client.put('/api/tailored/'+cv['id'],headers=bob,json={'title':'theft','content':'steal secrets please'}).status_code==404
    assert client.get('/api/tailored/'+cv['id']+'/export.pdf',headers=bob).status_code==404
    assert client.delete('/api/tailored/'+cv['id'],headers=bob).status_code==404
    updated=client.put('/api/tailored/'+cv['id'],headers=alice,json={'title':'Alice CV Revised','content':'Alice Smith\n\nPROFESSIONAL SUMMARY\nVerified: Primavera P6 coordination and MEP schedules.'})
    assert updated.status_code==200,updated.text
    assert updated.json()['title']=='Alice CV Revised'
    p=client.get('/api/tailored/'+cv['id']+'/export.pdf',headers=alice)
    assert p.status_code==200 and p.content.startswith(b'%PDF'),p.text[:250]
    text=' '.join(x.extract_text() or '' for x in PdfReader(io.BytesIO(p.content)).pages)
    assert 'Primavera P6 coordination' in text
    d=client.get('/api/tailored/'+cv['id']+'/export.docx',headers=alice)
    assert d.status_code==200 and d.content[:2]==b'PK'
    doc=Document(io.BytesIO(d.content))
    assert 'Alice CV Revised' not in '\n'.join(x.text for x in doc.paragraphs) # title not imposed as fabricated content
    assert any('Verified: Primavera P6' in x.text for x in doc.paragraphs)
    assert client.delete('/api/tailored/'+cv['id'],headers=alice).status_code==200
    assert client.get('/api/tailored/'+cv['id'],headers=alice).status_code==404
    assert len(client.get('/api/tailored',headers=alice).json())==1
    assert client.delete('/api/auth/account',headers=alice).status_code==200
    assert client.get('/api/tailored',headers=alice).status_code==401


def test_requires_actual_candidate_source_and_sufficient_job_description(client):
    admin=sign_up(client,'admin@example.com');promote('admin@example.com')
    job=create_job(client,admin)
    assert client.post(f'/api/jobs/{job}/tailor',headers=admin,json={'kind':'both'}).status_code==422
    client.put('/api/profile',headers=admin,json={'full_name':'Test Engineer','summary':'Construction scheduling specialist with Primavera P6 experience.'})
    r=client.post(f'/api/jobs/{job}/tailor',headers=admin,json={'kind':'cover_letter','tone':'formal'})
    assert r.status_code==200,r.text
    assert len(r.json()['documents'])==1
    short=create_job(client,admin,'P6')
    assert client.post(f'/api/jobs/{short}/tailor',headers=admin,json={'kind':'cv'}).status_code==422
    assert client.post(f'/api/jobs/{job}/tailor',headers=admin,json={'cv_id':'cv-someone-elses-doc'}).status_code==404
    assert client.post(f'/api/jobs/{job}/tailor',headers=admin,json={'kind':'magic'}).status_code==422
    assert client.put('/api/tailored/'+r.json()['documents'][0]['id'],headers=admin,json={'title':'x','content':'short'}).status_code==422

def test_ai_drafting_requires_explicit_consent_and_configuration(client,monkeypatch):
    h=sign_up(client,'optin@example.com');promote('optin@example.com')
    job=create_job(client,h)
    client.put('/api/profile',headers=h,json={'skills':'MEP, Primavera P6','summary':'MEP planning and Primavera P6 professional.'})
    url=f'/api/jobs/{job}/tailor'
    assert client.post(url,headers=h,json={'mode':'ai','allow_external_processing':False}).status_code==422
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    r=client.post(url,headers=h,json={'mode':'ai','allow_external_processing':True})
    assert r.status_code==503
    assert client.get('/api/tailored',headers=h).json()==[]
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key')
    async def mocked_ai(job,profile,cv,tone,confirmed,missing,skills):
        return {'cv':'TEST CV — verified candidate data\nMEP and Primavera P6 experience.\nProfessional summary based on candidate details.',
                'cover_letter':'Dear Hiring Manager,\nI am applying for the MEP Planning Engineer role at Example Engineering.\nMy documented background is in MEP and Primavera P6.\nSincerely, Test Candidate'}
    monkeypatch.setattr('server.tailor_ai.create_ai_drafts',mocked_ai)
    result=client.post(url,headers=h,json={'mode':'ai','allow_external_processing':True})
    assert result.status_code==200,result.text
    assert result.json()['method']=='opt-in external AI draft'
    assert len(result.json()['documents'])==2
