/** Explicitly labelled, offline-only UI demonstration. No real jobs or accounts. */
import * as SecureStore from 'expo-secure-store';

export const DEMO_JOBS = [
  {id:'demo-1',title:'MEP Planning Engineer — Demo vacancy',company:'Example Construction (Demo)',location:'Dubai',country:'UAE',description:'SAMPLE ONLY — This is not an actual vacancy. Example requirements: Primavera P6, MEP construction schedules, progress reporting, look-ahead plans, and delay analysis. Application links are disabled in demo mode.',url:'',source:'DEMO — NOT A LIVE JOB',first_seen_at:'2026-10-28T00:00:00Z'},
  {id:'demo-2',title:'Electrical Engineer — Demo vacancy',company:'Sample Engineering (Demo)',location:'Abu Dhabi',country:'UAE',description:'SAMPLE ONLY — No employer is recruiting through this demonstration. Example responsibilities: electrical design reviews, site inspections, technical submittals.',url:'',source:'DEMO — NOT A LIVE JOB',first_seen_at:'2026-10-28T00:00:00Z'},
  {id:'demo-3',title:'Project Coordinator — Demo vacancy',company:'Fictional Projects (Demo)',location:'Doha',country:'Qatar',description:'SAMPLE ONLY — A fictional vacancy used to demonstrate the job search and application tracker.',url:'',source:'DEMO — NOT A LIVE JOB',first_seen_at:'2026-10-28T00:00:00Z'},
];

type RecordObject=Record<string,unknown>;
type DemoState={saved:string[];alerts:RecordObject[];applications:RecordObject[];profile:RecordObject};
const initial:DemoState={saved:[],alerts:[],applications:[],profile:{full_name:'Demo User',headline:'Planning Engineer',country:'United Arab Emirates',city:'Dubai',desired_titles:'MEP Planning Engineer',skills:'Primavera P6, MEP',years_experience:2,salary_min:7000,salary_currency:'AED',summary:'A sample profile, stored on this device only.'}};
const storeKey='careerradar_offline_demo_v1';
async function getState():Promise<DemoState>{
  const raw=await SecureStore.getItemAsync(storeKey);
  if(!raw)return JSON.parse(JSON.stringify(initial)) as DemoState;
  try{return {...JSON.parse(JSON.stringify(initial)) as DemoState,...JSON.parse(raw)} as DemoState}catch{return JSON.parse(JSON.stringify(initial)) as DemoState}
}
async function putState(s:DemoState){await SecureStore.setItemAsync(storeKey,JSON.stringify(s))}
const nextId=()=>`demo-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
export async function demoRequest(path:string,method:string,body:unknown):Promise<unknown>{
  const s=await getState();
  const v=(body||{}) as RecordObject;
  if(path==='/integrations/status')return {inbox_oauth:'not_connected',whatsapp_business_api:'not_connected',routing_api:'not_connected'};
  if(path==='/walkins')return {items:[],note:'No fictional event listings.'};
  if(path==='/cv/shares')return [];
  if(path.startsWith('/reports/weekly'))return {weeks:Array.from({length:8},(_,i)=>({week_start:new Date(Date.now()-(7-i)*7*86400000).toISOString().slice(0,10),applications_added:0,jobs_saved:0,alerts_received:0})),due_followups:[],current_application_status_counts:{}};
  if(path==='/email/preview'&&method==='POST'){
    const text=(String(v.subject||'')+' '+String(v.body||'')).toLowerCase();
    const status=/regret to inform|not selected|not moving forward/.test(text)?'rejected':/interview/.test(text)?'interview':/offer letter|job offer/.test(text)?'offer':/thank you for applying|application received/.test(text)?'applied':'unknown';
    return {suggested_status:status,requires_confirmation:true,warning:'Offline sample analysis only. No email has been stored or application updated.'};
  }
  if(path==='/offers/check'&&method==='POST'){
    const text=String(v.text||'').toLowerCase();const flags=[];
    if(/visa fee|recruitment fee|processing fee|registration fee/.test(text))flags.push('Potential recruitment or processing fee request');
    if(/otp|bank pin|password/.test(text))flags.push('Potential request for private access details');
    return {warning_signs:flags,verified:false,official_portal:'https://www.mohre.gov.ae/',note:'Demo keyword check, not employer verification.'};
  }
  if(path.startsWith('/jobs/')&&path.endsWith('/application-kit')){
    const job=DEMO_JOBS.find(j=>path.includes(j.id));if(!job)throw Error('Demo vacancy not found');
    return {title:job.title,company:job.company,cover_letter_draft:`DEMONSTRATION DRAFT — NOT A REAL APPLICATION.\nDear Hiring Team,\n\nI would like to express interest in a role similar to ${job.title}. My declared profile lists ${s.profile.headline||'professional experience'} as my focus.\n\nKind regards,\n${s.profile.full_name||'[Your name]'}`,matching_declared_skills:[],notice:'Fictional example only. No application has been sent.'};
  }
  if(path.startsWith('/jobs/')&&path.endsWith('/roadmap')){
    return {steps:[{skill:'Primavera P6',next_step:'Study official documentation and create a practical work sample.'}],notice:'Demonstration-only skill suggestion; no real job requirements.'};
  }
  if(path.startsWith('/jobs/compare/batch')){
    const ids=new URLSearchParams(path.split('?')[1]).get('ids')?.split(',')||[];
    return {items:ids.map(id=>DEMO_JOBS.find(j=>j.id===id)).filter(Boolean).map(j=>({...j,trust:{freshness:'demo_only'}}))};
  }
  if(path.startsWith('/jobs/')&&path.endsWith('/trust'))return {freshness:'demo_only',employer_identity_verified:false,application_link_verified:false,notice:'Fictional demonstration vacancy.'};
  if(path.startsWith('/jobs/')&&path.endsWith('/activity'))return {employer_response_rate:null,hiring_activity_verified:false};
  if(path.startsWith('/jobs?')){
    const params=new URLSearchParams(path.slice(path.indexOf('?')+1));
    const q=(params.get('q')||'').toLowerCase();const loc=(params.get('location')||'').toLowerCase();
    return {items:DEMO_JOBS.filter(j=>(!q||`${j.title} ${j.company} ${j.description}`.toLowerCase().includes(q))&&(!loc||`${j.location} ${j.country}`.toLowerCase().includes(loc))),total:DEMO_JOBS.length,page:1};
  }
  if(path.startsWith('/jobs/')){
    const job=DEMO_JOBS.find(j=>j.id===decodeURIComponent(path.split('/').pop()||''));
    if(!job)throw Error('Demo vacancy not found');return job;
  }
  if(path==='/saved')return DEMO_JOBS.filter(j=>s.saved.includes(j.id));
  if(path.startsWith('/saved/')&&method==='POST'){const id=path.split('/').pop()||'';if(!DEMO_JOBS.find(j=>j.id===id))throw Error('Demo vacancy not found');if(!s.saved.includes(id))s.saved.push(id);await putState(s);return {ok:true}}
  if(path.startsWith('/saved/')&&method==='DELETE'){s.saved=s.saved.filter(id=>id!==path.split('/').pop());await putState(s);return {ok:true}}
  if(path==='/alerts'){
    if(method==='GET')return s.alerts;
    if(method==='POST'){s.alerts.push({id:nextId(),name:String(v.name||'My alert'),query:String(v.query||''),location:String(v.location||''),frequency:String(v.frequency||'daily')});await putState(s);return {ok:true}}
  }
  if(path.startsWith('/alerts/')&&method==='DELETE'){s.alerts=s.alerts.filter(a=>a.id!==path.split('/').pop());await putState(s);return {ok:true}}
  if(path==='/applications'){
    if(method==='GET')return s.applications;
    if(method==='POST'){s.applications.unshift({id:nextId(),title:String(v.title||''),company:String(v.company||''),status:String(v.status||'interested'),notes:String(v.notes||''),updated_at:new Date().toISOString()});await putState(s);return {ok:true}}
  }
  if(path.startsWith('/applications/')&&method==='PUT'){
    const item=s.applications.find(a=>a.id===path.split('/').pop());if(!item)throw Error('Application not found');Object.assign(item,v,{updated_at:new Date().toISOString()});await putState(s);return {ok:true}
  }
  if(path==='/profile'){
    if(method==='GET')return s.profile;
    if(method==='PUT'){s.profile={...s.profile,...v};await putState(s);return {ok:true}}
  }
  if(path==='/auth/login'||path==='/auth/register')return {token:'offline-demo',user:{id:'offline-demo',email:'demo@local.invalid',role:'seeker'}};
  if(path==='/auth/logout')return {ok:true};
  throw new Error('This feature requires a connected backend. Offline demo supports browsing, saved jobs, alerts, applications, and profile editing.');
}
