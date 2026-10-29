import * as SecureStore from 'expo-secure-store';
const key='cr_compare_jobs_v3';
export async function getCompared():Promise<string[]> {
  try {const ids=JSON.parse((await SecureStore.getItemAsync(key))||'[]');return Array.isArray(ids)?ids.filter(x=>typeof x==='string').slice(0,4):[]} catch{return []}
}
export async function toggleCompared(id:string){
  const ids=await getCompared();const present=ids.includes(id);
  if(!present&&ids.length>=4)throw Error('You can compare up to 4 jobs.');
  const updated=present?ids.filter(x=>x!==id):[...ids,id];
  await SecureStore.setItemAsync(key,JSON.stringify(updated));return updated;
}
export async function clearCompared(){await SecureStore.deleteItemAsync(key)}
