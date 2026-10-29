import React,{useState,useCallback} from 'react';
import {View,Text,TextInput,Pressable,ActivityIndicator} from 'react-native';
import {useFocusEffect,router} from 'expo-router';
import {call,Job} from '../../src/api';
import {Layout,Btn,Empty,C,st} from '../../src/ui';
export default function Discover(){const [query,setQuery]=useState(''),[city,setCity]=useState(''),[jobs,setJobs]=useState<Job[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
const search=useCallback(async()=>{setBusy(true);setError('');try{const data=await call<{items:Job[]}>('/jobs?'+new URLSearchParams({q:query,location:city,page:'1'}));setJobs(data.items)}catch(e){setError((e as Error).message)}finally{setBusy(false)}},[query,city]);
useFocusEffect(useCallback(()=>{search()},[]));
return <Layout title="Discover jobs" subtitle="Find your next opportunity across connected sources."><View style={{backgroundColor:'#2e59cb',borderRadius:18,padding:21,marginBottom:18}}><Text style={{color:'#fff',fontSize:21,fontWeight:'800'}}>A better job search starts here.</Text><Text style={{color:'#e2ebff',fontSize:12,lineHeight:21,marginTop:8}}>Save openings and organize your applications in one place.</Text></View>
<TextInput style={st.input} placeholder="Job title, keyword or skills" value={query} onChangeText={setQuery}/><TextInput style={st.input} placeholder="City, e.g. Dubai" value={city} onChangeText={setCity}/><Btn title={busy?'Searching…':'Search jobs →'} onPress={search} disabled={busy}/>
{error?<Text style={st.error}>{error}</Text>:null}{busy?<ActivityIndicator color={C.blue} style={{margin:16}}/>:null}
<View style={{marginTop:25}}><Text style={[st.jobtitle,{fontSize:18,marginBottom:12}]}>Available openings</Text>{!busy&&!jobs.length?<Empty title="No matching jobs yet" detail="Try different keywords or ask the administrator to connect approved job feeds."/>:jobs.map(j=><Pressable key={j.id} style={st.card} onPress={()=>router.push({pathname:'/job/[id]',params:{id:j.id}})}><Text style={st.jobtitle}>{j.title}</Text><Text style={st.meta}>{j.company} · {j.location||'Location unknown'}</Text><View style={[st.row,{marginTop:12}]}><Text style={{color:C.mint,fontWeight:'700',fontSize:11}}>{j.source}</Text><Text style={{color:C.blue,fontWeight:'800',fontSize:12}}>Details →</Text></View></Pressable>)}</View></Layout>}
