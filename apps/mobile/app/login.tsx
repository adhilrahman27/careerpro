import React,{useState} from 'react';
import {View,Text,SafeAreaView} from 'react-native';
import {router} from 'expo-router';
import {login} from '../src/api';
import {Field,Btn,st,C} from '../src/ui';
export default function Login(){const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[register,setRegister]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
const submit=async()=>{setBusy(true);setError('');try{await login(email,password,register);router.replace('/(tabs)')}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
return <SafeAreaView style={st.page}><View style={{flex:1,justifyContent:'center',padding:25}}><View style={st.card}><Text style={[st.title,{textAlign:'center'}]}>{register?'Create an account':'Welcome back'}</Text><Text style={[st.subtitle,{textAlign:'center'}]}>CareerRadar Pro</Text><Field label="Email" value={email} onChange={setEmail} placeholder="you@example.com"/><Field label="Password" value={password} onChange={setPassword} secure/>{error?<Text style={st.error}>{error}</Text>:null}<Btn title={busy?'Please wait…':register?'Register':'Sign in'} onPress={submit} disabled={busy||!email||password.length<10}/><View style={{marginTop:12}}><Btn outline title={register?'I have an account':'Create free account'} onPress={()=>setRegister(!register)}/></View><View style={{marginTop:12}}><Btn outline title="Browse jobs without signing in" onPress={()=>router.replace('/(tabs)')}/></View></View></View></SafeAreaView>}
