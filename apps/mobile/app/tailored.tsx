import React,{useCallback,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {router,useFocusEffect} from 'expo-router';
import {Layout,Btn,Empty,st} from '../src/ui';
import {call,DEMO_MODE} from '../src/api';
type Draft={id:string,title:string,kind:string,company:string,updated_at:string};
export default function TailoredLibrary(){
 const [items,setItems]=useState<Draft[]>([]),[error,setError]=useState('');
 useFocusEffect(useCallback(()=>{if(DEMO_MODE)return;(async()=>{try{setItems(await call<Draft[]>('/tailored'));setError('')}catch(e){setError((e as Error).message)}})()},[]));
 return <Layout title="Tailored documents" subtitle="Edit every application draft before sharing. PDF and Word exports are available in the web app.">
 <Btn title="← Go back" outline onPress={()=>router.back()}/><View style={{height:12}}/>
 {DEMO_MODE?<Empty title="Backend required" detail="Connect your own CareerRadar API server and upload a CV to generate real source-grounded documents."/>:null}
 {error?<Text style={st.error}>{error}</Text>:null}
 {!DEMO_MODE&&!items.length?<Empty title="No tailored documents yet" detail="Open a job and choose Tailor CV + Cover Letter to generate your first drafts."/>:null}
 {items.map(d=><View key={d.id} style={st.card}><Text style={st.jobtitle}>{d.title}</Text><Text style={st.meta}>{d.kind==='cv'?'CV':'Cover letter'} · {d.company}</Text><View style={{height:12}}/><Btn title="Open, edit & share" onPress={()=>router.push(('/document/'+d.id) as any)}/></View>)}
 </Layout>
}
