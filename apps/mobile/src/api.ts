import {demoRequest} from './demo';
import * as SecureStore from 'expo-secure-store';
export type Job={id:string;title:string;company:string;location:string;country:string;description:string;url:string;source:string;first_seen_at:string};
export type Application={id:string;company:string;title:string;status:string;notes:string;updated_at:string};
export type Alert={id:string;name:string;query:string;location:string;frequency:string};
export type Profile={full_name:string;headline:string;country:string;city:string;desired_titles:string;skills:string;years_experience:number;salary_min:number|null;salary_currency:string;summary:string};
const base=(process.env.EXPO_PUBLIC_API_BASE_URL||'').replace(/\/$/,'');
export const configured=Boolean(base&&(base.startsWith('https://')||base.startsWith('http://10.0.2.2:')));
export const DEMO_MODE=!configured;
export async function call<T>(path:string,method='GET',body?:unknown):Promise<T>{
 if(DEMO_MODE) return await demoRequest(path,method,body) as T;
 const token=await SecureStore.getItemAsync('cr_token');
 let response:Response;
 try{response=await fetch(base+'/api'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body)});}catch{throw new Error('Could not connect to CareerRadar. Check internet and server URL.');}
 const payload=await response.json().catch(()=>({}));
 if(!response.ok){if(response.status===401)await SecureStore.deleteItemAsync('cr_token');throw new Error(typeof payload.detail==='string'?payload.detail:'Request failed ('+response.status+')');}
 return payload as T;
}
export async function login(email:string,password:string,register=false){if(DEMO_MODE){return {token:'offline-demo',user:{id:'offline-demo',email:'demo@local.invalid',role:'seeker'}}}const r=await call<{token:string;user:{id:string;email:string;role:string}}>(register?'/auth/register':'/auth/login','POST',{email,password});await SecureStore.setItemAsync('cr_token',r.token);return r;}
export async function logout(){if(DEMO_MODE)return;try{await call('/auth/logout','POST')}finally{await SecureStore.deleteItemAsync('cr_token')}}
export async function getToken(){return DEMO_MODE?'offline-demo':await SecureStore.getItemAsync('cr_token')}
