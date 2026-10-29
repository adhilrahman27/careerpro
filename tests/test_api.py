import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from server import db
from server.main import app, _throttle
from server.security import token_digest

@pytest.fixture()
def client(tmp_path,monkeypatch):
    _throttle.clear()
    monkeypatch.setattr(db,'DB_PATH',str(tmp_path/'unit.sqlite'))
    monkeypatch.setattr('server.main.UPLOAD',tmp_path/'uploads')
    with TestClient(app) as c:yield c

def user(client,email='one@example.com',password='strong-password-1'):
    r=client.post('/api/auth/register',json={'email':email,'password':password});assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_auth_validation_isolation_logout(client):
    assert client.post('/api/auth/register',json={'email':'invalid','password':'123'}).status_code==422
    h1=user(client);h2=user(client,'two@example.com')
    assert client.get('/api/auth/me').status_code==401
    assert client.get('/api/profile',headers=h1).status_code==200
    assert client.put('/api/profile',headers=h1,json={'full_name':'Alice','skills':'P6, Primavera'}).status_code==200
    assert client.get('/api/profile',headers=h2).json()['full_name']==''
    assert client.post('/api/auth/login',json={'email':'one@example.com','password':'incorrect123'}).status_code==401
    assert client.post('/api/auth/logout',headers=h1).status_code==200
    assert client.get('/api/profile',headers=h1).status_code==401

def test_admin_search_saved_and_match(client):
    from server.bootstrap_admin import promote
    h=user(client);promote('one@example.com')
    j=client.post('/api/admin/jobs',headers=h,json={'company':'Acme Engineering','title':'MEP Planning Engineer','location':'Dubai','country':'United Arab Emirates','url':'https://example.com/careers/123','description':'Primavera P6 and MEP coordination'})
    assert j.status_code==200,j.text
    jid=j.json()['id']
    assert client.get('/api/jobs?q=planning&location=Dubai').json()['total']==1
    assert client.get('/api/jobs?q=mechanical').json()['total']==0
    client.put('/api/profile',headers=h,json={'city':'Dubai','skills':'P6,Primavera','desired_titles':'Planning Engineer'})
    m=client.get(f'/api/match/{jid}',headers=h)
    assert m.status_code==200,m.text
    assert m.json()['score']>40
    assert client.post('/api/applications',headers=h,json={'job_id':jid,'company':'Acme Engineering','title':'Planning Engineer','status':'interested'}).status_code==200
    assert client.post(f'/api/saved/{jid}',headers=h).status_code==200
    assert len(client.get('/api/saved',headers=h).json())==1
    assert client.delete(f'/api/saved/{jid}',headers=h).status_code==200
    assert not client.get('/api/saved',headers=h).json()
    h2=user(client,'other@example.com')
    assert client.get('/api/admin/overview',headers=h2).status_code==403
    assert client.post('/api/admin/jobs',headers=h2,json={'company':'X','title':'X','url':'https://example.com'}).status_code==403

def test_alerts_worker_deduplicates(client):
    from server.bootstrap_admin import promote
    from server.worker import process_alerts
    h=user(client);promote('one@example.com')
    r=client.post('/api/admin/jobs',headers=h,json={'company':'ABC','title':'Junior Planning Engineer','location':'Dubai','url':'https://example.com/abc'})
    jid=r.json()['id']
    a=client.post('/api/alerts',headers=h,json={'name':'planning','query':'Planning','location':'Dubai','frequency':'daily'})
    assert a.status_code==200
    assert process_alerts()==1
    assert process_alerts()==0
    n=client.get('/api/notifications',headers=h).json()
    assert len(n)==1 and n[0]['job_id']==jid
    assert client.post('/api/notifications/'+n[0]['id']+'/read',headers=h).status_code==200
    assert client.delete('/api/alerts/'+a.json()['id'],headers=h).status_code==200

def test_applications_cv_and_deletion(client):
    h1=user(client);h2=user(client,'other@example.com')
    body={'company':'Engineering Corp','title':'Scheduler','status':'applied','notes':'Applied on employer website'}
    a=client.post('/api/applications',headers=h1,json=body)
    assert a.status_code==200,a.text
    aid=a.json()['id']
    assert client.get('/api/applications',headers=h2).json()==[]
    assert client.put('/api/applications/'+aid,headers=h2,json=body).status_code==404
    body['status']='interview'
    assert client.put('/api/applications/'+aid,headers=h1,json=body).status_code==200
    assert client.get('/api/applications/export.csv',headers=h1).status_code==200
    upload=client.post('/api/cv/upload',headers=h1,files={'file':('cv.txt',b'MEP Planning Engineer with Primavera P6','text/plain')})
    assert upload.status_code==200,upload.text
    cid=upload.json()['id']
    assert client.get('/api/cv/'+cid+'/download',headers=h2).status_code==404
    assert client.get('/api/cv/'+cid+'/download',headers=h1).content.startswith(b'MEP')
    assert client.get('/api/cv/resume/generate.pdf',headers=h1).content.startswith(b'%PDF')
    assert client.get('/api/account/export',headers=h1).status_code==200
    assert client.delete('/api/auth/account',headers=h1).status_code==200
    assert client.get('/api/profile',headers=h1).status_code==401

def test_provider_safety(client):
    from server.bootstrap_admin import promote
    h=user(client);promote('one@example.com')
    assert client.post('/api/admin/providers',headers=h,json={'kind':'lever','slug':'../../evil','display_name':'Bad'}).status_code==422
    assert client.post('/api/admin/jobs',headers=h,json={'company':'X','title':'X','url':'http://insecure.example.com'}).status_code>=400
    r=client.post('/api/admin/providers',headers=h,json={'kind':'greenhouse','slug':'examplecorp','display_name':'Example'})
    assert r.status_code==200,r.text

def test_greenhouse_and_lever_adapters_without_network(monkeypatch):
    import asyncio
    from server import sources
    class Response:
        def __init__(self,body):self.body=body
        def raise_for_status(self):pass
        def json(self):return self.body
    class MockClient:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url):
            if 'greenhouse' in url:
                return Response({'jobs':[{'id':101,'title':'Planning Engineer','location':{'name':'Dubai'},'absolute_url':'https://job-boards.greenhouse.io/example/jobs/101','content':'<p>Primavera <b>P6</b></p>'}]})
            return Response([{'id':'test-lever-1','text':'Civil Engineer','hostedUrl':'https://jobs.lever.co/example/test-lever-1','categories':{'location':'Abu Dhabi'},'descriptionPlain':'Civil engineering'}])
    monkeypatch.setattr(sources.httpx,'AsyncClient',MockClient)
    g=asyncio.run(sources.fetch_jobs('greenhouse','example'))
    l=asyncio.run(sources.fetch_jobs('lever','example'))
    assert len(g)==1 and g[0]['title']=='Planning Engineer' and '<' not in g[0]['description']
    assert len(l)==1 and l[0]['location']=='Abu Dhabi'
    with pytest.raises(ValueError):asyncio.run(sources.fetch_jobs('greenhouse','../../malicious'))
