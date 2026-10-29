"""Optional browser/API integration smoke. Run: PYTHONPATH=. python tests/browser_smoke.py
Exercises real FastAPI requests via a host bridge because this build sandbox blocks
Chromium's localhost navigation. This is not a production server E2E test.
"""
import tempfile,base64
from pathlib import Path
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from server import db
from server.main import app,_throttle

ROOT=Path(__file__).resolve().parents[1]
web=ROOT/'web'
css=(web/'assets/style.css').read_text()
js=(web/'assets/app.js').read_text()
html=(web/'index.html').read_text().replace('<link rel="stylesheet" href="/assets/style.css">','<style>'+css+'</style>').replace('<script src="/assets/app.js" defer></script>','').replace('<img src="/assets/icon.svg"','<img src="data:image/svg+xml;base64,'+base64.b64encode((web/'assets/icon.svg').read_bytes()).decode()+'"')

def run():
 with tempfile.TemporaryDirectory() as temp:
  db.DB_PATH=str(Path(temp)/'smoke.sqlite');_throttle.clear()
  with TestClient(app) as client, sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1280,'height':900})
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def bridge(url,method,headers,body):
    kw={'headers':headers or {}}
    if body is not None:kw['content']=body
    r=client.request(method,url,**kw)
    try:payload=r.json()
    except:payload={}
    return {'status':r.status_code,'content_type':r.headers.get('content-type','application/json'),'payload':payload}
   page.expose_function('nativeRequest',bridge)
   page.set_content(html,wait_until='domcontentloaded')
   page.evaluate('''() => {
     for(const kind of ['sessionStorage','localStorage'])Object.defineProperty(window,kind,{value:{storage:{},getItem(k){return this.storage[k]||null},setItem(k,v){this.storage[k]=String(v)},removeItem(k){delete this.storage[k]}}});
     window.fetch=async(url,opt={})=>{let x=await window.nativeRequest(url,opt.method||'GET',opt.headers||{},opt.body??null);return {ok:x.status>=200&&x.status<300,status:x.status,headers:{get:()=>x.content_type},json:async()=>x.payload}};
     Object.defineProperty(navigator,'serviceWorker',{value:{register:()=>Promise.resolve()}});
   }''')
   page.evaluate(js)
   page.get_by_role('button',name='Sign in / Register').click()
   page.get_by_role('button',name='Create account',exact=True).click()
   page.locator('#f-email').fill('browser@example.com')
   page.locator('#f-password').fill('very-strong-passphrase-123')
   page.get_by_role('button',name='Create free account').click()
   page.wait_for_timeout(450)
   assert 'Professional profile' in page.locator('#page').inner_text(),page.locator('#page').inner_text()[:400]
   page.locator('#f-full_name').fill('Browser Tester')
   page.locator('#f-skills').fill('Primavera P6')
   page.get_by_role('button',name='Save my profile').click()
   page.wait_for_timeout(200)
   page.get_by_role('button',name='Job alerts').click()
   page.get_by_role('button',name='+ Create alert').click()
   page.locator('#f-name').fill('Planning roles')
   page.locator('#f-query').fill('Planning')
   page.locator('#f-location').fill('Dubai')
   page.get_by_role('button',name='Create alert',exact=True).click()
   page.wait_for_timeout(200)
   assert 'Planning roles' in page.locator('#page').inner_text(),page.locator('#page').inner_text()
   page.get_by_role('button',name='Applications').click()
   page.get_by_role('button',name='+ New application').click()
   page.locator('#f-company').fill('Test Engineering')
   page.locator('#f-title').fill('Planning Engineer')
   page.get_by_role('button',name='Track application').click()
   page.wait_for_timeout(200)
   assert 'Test Engineering' in page.locator('#page').inner_text(),page.locator('#page').inner_text()
   # New 0.3 career tools and server-backed reports.
   page.get_by_role('button',name='Career tools').click()
   page.wait_for_timeout(250)
   assert 'Career tools' in page.locator('#page').inner_text()
   page.screenshot(path=str(ROOT/'docs'/'career-tools-desktop.png'),full_page=True)
   page.get_by_role('button',name='Review an email').click()
   page.locator('#f-subject').fill('Interview invitation')
   page.locator('#f-body').fill('We invite you to an interview next week.')
   page.get_by_role('button',name='Classify email').click()
   page.wait_for_timeout(180)
   assert 'interview' in page.locator('#mail-result').inner_text()
   page.get_by_role('button',name='Confirm change').click()
   page.wait_for_timeout(180)
   page.get_by_role('button',name='View weekly report').click()
   page.wait_for_timeout(180)
   assert 'Weekly job-search report' in page.locator('#page').inner_text()
   page.get_by_role('button',name='Walk-in interviews').click()
   page.wait_for_timeout(180)
   assert 'No reviewed walk-in interviews yet' in page.locator('#page').inner_text()
   page.get_by_role('button',name='Career tools').click()
   page.wait_for_timeout(150)
   page.set_viewport_size({'width':390,'height':844})
   page.screenshot(path=str(ROOT/'docs'/'career-tools-mobile.png'),full_page=True)
   assert not errors,errors
   print('BROWSER_SMOKE_PASS: registration → profile → alert → application → email review → insights → walk-in → mobile career tools')
   browser.close()

if __name__=='__main__':run()
