"""Test job -> modal -> generated CV + cover letter -> edit/save. Browser uses a
FastAPI TestClient bridge (not a native device or live deployment).
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from server import db
from server.main import app,_throttle
from server.bootstrap_admin import promote

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'
css=(WEB/'assets/style.css').read_text()
js=(WEB/'assets/app.js').read_text()
html=(WEB/'index.html').read_text().replace('<link rel="stylesheet" href="/assets/style.css">','<style>'+css+'</style>').replace('<script src="/assets/app.js" defer></script>','')
html=html.replace('<img src="/assets/icon.svg"','<img src="data:image/svg+xml;base64,'+base64.b64encode((WEB/'assets/icon.svg').read_bytes()).decode()+'"')

def main():
 with TemporaryDirectory() as temp:
  db.DB_PATH=str(Path(temp)/'qa.sqlite');_throttle.clear()
  with TestClient(app) as client:
   reg=client.post('/api/auth/register',json={'email':'tailortester@example.com','password':'Strong-Passphrase-5678'})
   assert reg.status_code==200,reg.text
   token=reg.json()['token'];headers={'Authorization':'Bearer '+token}
   promote('tailortester@example.com')
   client.put('/api/profile',headers=headers,json={'full_name':'Alex Taylor','headline':'MEP Planning Engineer','summary':'Planning engineer coordinating MEP construction schedules using Primavera P6.','skills':'Primavera P6, MEP, Scheduling'})
   cv=client.post('/api/cv/upload',headers=headers,files={'file':('me.txt',b'Alex Taylor\nMEP Planner, Site Schedules\nSkilled in Primavera P6 and construction planning.\nEducation: Engineering degree\n','text/plain')})
   assert cv.status_code==200,cv.text
   vacancy=client.post('/api/admin/jobs',headers=headers,json={'company':'Example Building','title':'MEP Planning Engineer','description':'Seeking a planning engineer with Primavera P6, MEP and Power BI skills for monthly schedules and weekly progress reports.','location':'Dubai','url':'https://example.com/career/test'})
   assert vacancy.status_code==200,vacancy.text
   with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':860})
    errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
    def bridge(url,method,headers,body):
     req={'headers':headers or {}}
     if body is not None:req['content']=body
     res=client.request(method,url,**req)
     try:payload=res.json()
     except:payload={}
     return {'status':res.status_code,'content_type':res.headers.get('content-type','application/json'),'payload':payload}
    page.expose_function('nativeRequest',bridge)
    page.set_content(html,wait_until='domcontentloaded')
    page.evaluate('''() => {
     for(const kind of ['sessionStorage','localStorage'])Object.defineProperty(window,kind,{value:{storage:{},getItem(k){return this.storage[k]||null},setItem(k,v){this.storage[k]=String(v)},removeItem(k){delete this.storage[k]}}});
     window.fetch=async(url,opt={})=>{const r=await window.nativeRequest(url,opt.method||'GET',opt.headers||{},opt.body??null);return {ok:r.status>=200&&r.status<300,status:r.status,headers:{get:()=>r.content_type},json:async()=>r.payload}};
     Object.defineProperty(navigator,'serviceWorker',{value:{register:()=>Promise.resolve()}});
    }''')
    page.evaluate('token=>sessionStorage.setItem("cr_token",token)',token)
    page.evaluate(js)
    page.wait_for_timeout(350)
    page.get_by_role('button',name='Details ↗').click()
    page.get_by_role('button',name='✎ Tailor CV + Letter').click()
    page.locator('#tailor-cv').select_option(cv.json()['id'])
    page.locator('#tailor-kind').select_option('both')
    page.get_by_role('button',name='Create editable drafts').click()
    page.wait_for_timeout(400)
    assert page.locator('#draft-edit').count()==1,page.locator('body').inner_text()[-500:]
    assert 'Primavera P6' in page.locator('#draft-content').input_value()
    assert 'Power BI' not in page.locator('#draft-content').input_value()
    page.locator('#draft-content').fill(page.locator('#draft-content').input_value()+'\nREVIEWED BY APPLICANT.')
    page.get_by_role('button',name='Save edits').click()
    page.wait_for_timeout(250)
    assert 'Tailored CVs & cover letters' in page.locator('#page').inner_text()
    assert len(client.get('/api/tailored',headers=headers).json())==2
    page.screenshot(path=str(ROOT/'docs'/'tailored-documents-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':840})
    page.screenshot(path=str(ROOT/'docs'/'tailored-documents-mobile.png'),full_page=True)
    assert not errors,errors
    print('TAILORING_BROWSER_PASS: job detail -> select CV -> generate both documents -> edit/save -> library; no browser errors')
    browser.close()
if __name__=='__main__':main()
