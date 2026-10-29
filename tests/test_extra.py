from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
import pytest
from server import db
from server.main import app,_throttle
from server.bootstrap_admin import promote
from server.worker import process_followups

@pytest.fixture()
def c(tmp_path,monkeypatch):
    _throttle.clear()
    monkeypatch.setattr(db,'DB_PATH',str(tmp_path/'unit.sqlite'))
    monkeypatch.setattr('server.main.UPLOAD',tmp_path/'uploads')
    with TestClient(app) as client: yield client

def register(c,mail):
    r=c.post('/api/auth/register',json={'email':mail,'password':'strong-password-123'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def job(c,h,company,title,desc='Primavera P6 and Power BI'):
    r=c.post('/api/admin/jobs',headers=h,json={'company':company,'title':title,'location':'Dubai','country':'UAE','url':'https://example.com/jobs/'+title.lower().replace(' ','-'),'description':desc})
    assert r.status_code==200,r.text
    return r.json()['id']

def test_job_trust_activity_comparison_and_directions(c):
    h=register(c,'admin@example.com');promote('admin@example.com')
    a=job(c,h,'Acme','Planning Engineer');b=job(c,h,'TestCo','MEP Engineer')
    trust=c.get('/api/jobs/'+a+'/trust').json()
    assert trust['employer_identity_verified'] is False and trust['application_link_verified'] is False
    assert trust['freshness']=='recently_seen'
    act=c.get('/api/jobs/'+a+'/activity').json()
    assert act['employer_response_rate'] is None
    r=c.get('/api/jobs/compare/batch?ids='+a+','+b)
    assert r.status_code==200,r.text
    assert len(r.json()['items'])==2
    assert c.get('/api/jobs/compare/batch?ids='+a+','+a).status_code==422
    mapurl=c.get('/api/commute/directions',params={'origin':'Sharjah','job_id':a,'mode':'transit'}).json()
    assert mapurl['estimated_minutes'] is None and 'google.com/maps/dir/' in mapurl['url']
    assert 'travelmode=transit' in mapurl['url']
    assert c.get('/api/commute/directions',params={'origin':'','job_id':a}).status_code==422


def test_job_drafts_roadmap_offer_and_mail_confirm(c):
    h=register(c,'admin@example.com');promote('admin@example.com')
    other=register(c,'other@example.com')
    jid=job(c,h,'Acme','Planning Engineer')
    c.put('/api/profile',headers=h,json={'full_name':'Test Candidate','headline':'Planning Engineer','skills':'Primavera P6, Excel'})
    kit=c.get('/api/jobs/'+jid+'/application-kit',headers=h)
    assert kit.status_code==200
    assert 'Test Candidate' in kit.json()['cover_letter_draft']
    assert 'Primavera P6' in kit.json()['matching_declared_skills']
    assert 'No application was sent' in kit.json()['notice']
    roadmap=c.get('/api/jobs/'+jid+'/roadmap',headers=h).json()
    assert 'Power BI' in roadmap['not_in_declared_profile']
    assert 'Primavera P6' not in roadmap['not_in_declared_profile']
    warning=c.post('/api/offers/check',headers=h,json={'text':'You must pay a visa fee before starting work.'})
    assert warning.status_code==200 and warning.json()['verified'] is False
    assert warning.json()['warning_signs']
    appid=c.post('/api/applications',headers=h,json={'company':'Acme','title':'Planning Engineer'}).json()['id']
    preview=c.post('/api/email/preview',headers=h,json={'subject':'Invitation to interview','body':'We invite you to an interview for the role.'})
    assert preview.json()['suggested_status']=='interview'
    data={'sender':'HR','subject':'Interview invitation','body':'Please schedule an interview','application_id':appid,'status':'interview'}
    assert c.post('/api/email/confirm',headers=other,json=data).status_code==404
    assert c.post('/api/email/confirm',headers=h,json=data).status_code==200
    assert c.get('/api/applications',headers=h).json()[0]['status']=='interview'
    assert c.post('/api/email/confirm',headers=h,json={**data,'subject':'Hello','body':'Just saying hello'}).status_code==422


def test_walkins_admin_review_and_whatsapp_share(c):
    h=register(c,'admin@example.com');promote('admin@example.com')
    user=register(c,'seeker@example.com')
    jid=job(c,h,'Acme','Planning Engineer')
    event={'company':'Acme','title':'Planning Engineer','venue':'Business Centre','city':'Dubai','country':'UAE',
       'starts_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),
       'ends_at':(datetime.now(timezone.utc)+timedelta(days=2,hours=2)).isoformat(),
       'source_url':'https://example.com/events','requirements':'P6','documents':'Resume','moderator_reviewed':False}
    assert c.post('/api/admin/walkins',json=event,headers=user).status_code==403
    r=c.post('/api/admin/walkins',json=event,headers=h)
    assert r.status_code==200,r.text
    eid=r.json()['id']
    assert not c.get('/api/walkins').json()['items']
    assert c.post('/api/admin/walkins/'+eid+'/publish',headers=h).status_code==200
    assert len(c.get('/api/walkins').json()['items'])==1
    share=c.post('/api/integrations/whatsapp/preview',headers=user,json={'job_id':jid}).json()
    assert share['automatic_delivery'] is False and 'api.whatsapp.com' in share['url']
    integrations=c.get('/api/integrations/status').json()
    assert integrations['whatsapp_business_api']=='not_connected'


def test_cv_shares_private_expire_revoke_and_weekly(c):
    h=register(c,'one@example.com');other=register(c,'other@example.com')
    cv=c.post('/api/cv/upload',headers=h,files={'file':('resume.txt',b'My skills: P6 and coordination','text/plain')}).json()['id']
    assert c.get('/api/cv/shares',headers=other).json()==[]
    share=c.post('/api/cv/shares',headers=h,json={'cv_id':cv,'expires_days':1,'max_opens':1})
    assert share.status_code==200,share.text
    link=share.json()['path']
    assert c.get(link).status_code==200
    assert c.get(link).status_code==404
    assert c.delete('/api/cv/shares/'+share.json()['id'],headers=other).status_code==404
    assert c.delete('/api/cv/shares/'+share.json()['id'],headers=h).status_code==200
    more=c.post('/api/cv/shares',headers=h,json={'cv_id':cv,'expires_days':7,'max_opens':3}).json()
    assert c.get(more['path']).content.startswith(b'My skills')
    assert c.delete('/api/cv/shares/'+more['id'],headers=h).status_code==200
    assert c.get(more['path']).status_code==404
    assert c.get('/api/public/cv-share/invalid').status_code==404
    appid=c.post('/api/applications',headers=h,json={'company':'Acme','title':'P6 Engineer',
      'follow_up_at':(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()}).json()['id']
    assert process_followups()==1
    assert process_followups()==0
    report=c.get('/api/reports/weekly?weeks=4',headers=h).json()
    assert len(report['weeks'])==4
    assert len(report['due_followups'])==1
    assert report['current_application_status_counts']['interested']==1
    assert c.get('/api/reports/weekly',headers=other).json()['due_followups']==[]
    assert c.delete('/api/auth/account',headers=h).status_code==200
    assert c.get(more['path']).status_code==404
