import React,{useCallback,useState} from 'react';
import {Alert,Text,View,Pressable} from 'react-native';
import {router,useLocalSearchParams,useFocusEffect} from 'expo-router';
import {Layout,Btn,st,C,Empty} from '../../src/ui';
import {call,DEMO_MODE,Job} from '../../src/api';

type OriginalCV={id:string,filename:string};
export default function TailorJob(){
 const {id}=useLocalSearchParams<{id:string}>();
 const [job,setJob]=useState<Job|null>(null),[cvs,setCvs]=useState<OriginalCV[]>([]),
 [cv,setCv]=useState(''),[tone,setTone]=useState('professional'),[kind,setKind]=useState('both'),
 [error,setError]=useState(''),[busy,setBusy]=useState(false),[aiEnabled,setAiEnabled]=useState(false),[mode,setMode]=useState('local'),[consent,setConsent]=useState(false);
 useFocusEffect(useCallback(()=>{if(!id||DEMO_MODE)return;(async()=>{try{const [j,docs,features]=await Promise.all([call<Job>('/jobs/'+encodeURIComponent(id)),call<OriginalCV[]>('/cv'),call<{ai_cv_tailoring:boolean}>('/features')]);setAiEnabled(Boolean(features.ai_cv_tailoring));setJob(j);setCvs(docs);setCv(docs.length?docs[0].id:'');setError('')}catch(e){setError((e as Error).message)}})()},[id]));
 const create=async()=>{if(!id||busy)return;setBusy(true);setError('');try{const result=await call<{documents:{id:string}[]}>('/jobs/'+encodeURIComponent(id)+'/tailor','POST',{cv_id:cv||null,tone,kind,mode,allow_external_processing:consent});if(result.documents.length)router.replace(('/document/'+result.documents[0].id) as any)}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 const selector=(items:{value:string,label:string}[],value:string,onChange:(s:string)=>void)=> <View style={{flexDirection:'row',flexWrap:'wrap',gap:7,marginBottom:13}}>{items.map(option=><Pressable key={option.value} onPress={()=>onChange(option.value)} style={{padding:10,borderRadius:10,backgroundColor:value===option.value?'#dce9ff':'white',borderWidth:1,borderColor:value===option.value?C.blue:C.line}}><Text style={{fontSize:12,color:C.navy}}>{option.label}</Text></Pressable>)}</View>;
 return <Layout title="Tailor CV + Letter" subtitle="The selected job description is matched with the skills and facts in your CV and saved profile.">
 {DEMO_MODE?<Empty title="Connect live backend" detail="This feature cannot generate genuine job-specific documents from fictional demo jobs. Configure the CareerRadar server first."/>:<View style={st.card}>
 {job?<><Text style={st.jobtitle}>{job.title}</Text><Text style={st.meta}>{job.company} · {job.location}</Text></>:null}
 <Text style={[st.label,{marginTop:18}]}>Original CV</Text>
 {selector([{value:'',label:'My profile only'},...cvs.map(d=>({value:d.id,label:d.filename}))],cv,setCv)}
 <Text style={st.label}>Create</Text>
 {selector([{value:'both',label:'Both documents'},{value:'cv',label:'CV only'},{value:'cover_letter',label:'Cover letter only'}],kind,setKind)}
 <Text style={st.label}>Writing style</Text>
 {selector([{value:'professional',label:'Professional'},{value:'concise',label:'Concise'},{value:'formal',label:'Formal'}],tone,setTone)}
 <Text style={st.label}>Generation</Text>
 {selector([{value:'local',label:'Private / local matching'},...(aiEnabled?[{value:'ai',label:'AI-enhanced rewrite'}]:[])],mode,setMode)}
 {mode==='ai'?<Text style={[st.meta,{marginBottom:12}]} onPress={()=>setConsent(!consent)}>{consent?'☑':'☐'} I consent to sending my CV, profile and this job to the configured external AI provider for tailoring.</Text>:null}
 <Text style={[st.meta,{marginBottom:16}]}>Uses only evidence from your uploaded resume/profile. Review and edit all text. No job application will be submitted.</Text>
 {error?<Text style={st.error}>{error}</Text>:null}
 <Btn title={busy?'Generating…':'Create editable document(s)'} disabled={busy} onPress={create}/>
 <View style={{height:10}}/><Btn title="View my drafts" outline onPress={()=>router.push('/tailored' as any)}/>
 </View>}
 </Layout>
}
