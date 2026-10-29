import React,{useCallback,useState} from 'react';
import {Text,Pressable,View,ActivityIndicator} from 'react-native';
import {router,useFocusEffect} from 'expo-router';
import {call,Job,getToken} from '../../src/api';
import {Layout,Btn,Empty,C,st} from '../../src/ui';
export default function Saved(){const [jobs,setJobs]=useState<Job[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState('');
const load=useCallback(async()=>{setLoading(true);try{if(!await getToken()){setError('Sign in to view saved jobs.');return}setJobs(await call<Job[]>('/saved'));setError('')}catch(e){setError((e as Error).message)}finally{setLoading(false)}},[]);
useFocusEffect(load);
return <Layout title="Saved jobs" subtitle="Your personal shortlist.">{loading?<ActivityIndicator color={C.blue}/>:error?<><Text style={st.error}>{error}</Text><Btn title="Sign in" onPress={()=>router.push('/login')}/></>:jobs.length?jobs.map(j=><Pressable style={st.card} key={j.id} onPress={()=>router.push({pathname:'/job/[id]',params:{id:j.id}})}><Text style={st.jobtitle}>{j.title}</Text><Text style={st.meta}>{j.company} · {j.location}</Text></Pressable>):<Empty title="No saved jobs yet" detail="Tap Save on a vacancy to add it to your shortlist."/>}</Layout>}
