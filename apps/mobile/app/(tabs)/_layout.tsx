import React from 'react';
import {Tabs} from 'expo-router';
import {Text} from 'react-native';
import {C} from '../../src/ui';
const icons:Record<string,string>={index:'⌕',saved:'♡',alerts:'♧',applications:'▤',profile:'♙',tools:'✦'};
export default function TabsLayout(){return <Tabs screenOptions={({route})=>({headerShown:false,tabBarActiveTintColor:C.blue,tabBarInactiveTintColor:'#8191a8',tabBarStyle:{borderTopColor:C.line,height:65,paddingBottom:8},tabBarIcon:({color})=><Text style={{color,fontSize:23}}>{icons[route.name]||'○'}</Text>})}>
<Tabs.Screen name="index" options={{title:'Discover'}}/><Tabs.Screen name="saved" options={{title:'Saved'}}/><Tabs.Screen name="alerts" options={{title:'Alerts'}}/><Tabs.Screen name="applications" options={{title:'Applications'}}/><Tabs.Screen name="profile" options={{title:'Profile'}}/><Tabs.Screen name="tools" options={{title:'Tools'}}/></Tabs>}
