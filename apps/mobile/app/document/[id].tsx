import React,{useCallback,useState} from 'react';
import {Share,Alert,Text,TextInput,View} from 'react-native';
import {router,useLocalSearchParams,useFocusEffect} from 'expo-router';
import {Layout,Btn,st} from '../../src/ui';
import {call,DEMO_MODE} from '../../src/api';
export default function EditTailored(){
 const {id}=useLocalSearchParams<{id:string}>();
 const [title,setTitle]=useState(''),[content,setContent]=useState(''),[kind,setKind]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useFocusEffect(useCallback(()=>{if(!id||DEMO_MODE)return;(async()=>{try{const d=await call<{title:string,content:string,kind:string}>('/tailored/'+encodeURIComponent(id));setTitle(d.title);setContent(d.content);setKind(d.kind);setError('')}catch(e){setError((e as Error).message)}})()},[id]));
 const save=async()=>{setBusy(true);try{await call('/tailored/'+encodeURIComponent(id),'PUT',{title,content});setError('');return true}catch(e){setError((e as Error).message);return false}finally{setBusy(false)}};
 return <Layout title="Edit document" subtitle="Save a job-specific draft, then use the Android share sheet or export a PDF/Word file from the website.">
 <View style={st.card}><Text style={st.label}>Document title</Text><TextInput style={st.input} value={title} onChangeText={setTitle}/><Text style={st.label}>Editable {kind==='cv'?'CV':'cover letter'} text</Text><TextInput multiline textAlignVertical="top" style={[st.input,{minHeight:360}]} value={content} onChangeText={setContent}/>
 {error?<Text style={st.error}>{error}</Text>:null}
 <Btn title={busy?'Saving…':'Save document'} disabled={busy} onPress={async()=>{if(await save())Alert.alert('Saved','Your document is stored privately.')}}/>
 <View style={{height:10}}/>
 <Btn title="Save and share text" outline disabled={busy} onPress={async()=>{if(await save())await Share.share({title,message:content})}}/>
 <View style={{height:10}}/>
 <Btn title="All tailored documents" outline onPress={()=>router.replace('/tailored' as any)}/>
 <Text style={[st.meta,{marginTop:15}]}>Native export to PDF/DOCX isn't bundled yet. The authenticated website supports both formats.</Text></View>
 </Layout>
}
