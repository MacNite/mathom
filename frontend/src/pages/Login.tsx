import { useState } from 'react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
export default function Login() {
 const {status,refresh,login}=useAuth(); const[email,setEmail]=useState('');const[password,setPassword]=useState('');const[error,setError]=useState('');const[busy,setBusy]=useState(false);
 const submit=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{await api.localLogin(email,password);await refresh();}catch{setError('Invalid email or password.')}finally{setBusy(false)}};
 return <div className="flex min-h-screen items-center justify-center p-6"><div className="card w-full max-w-md text-center"><div className="mb-2 text-4xl">🏡</div><h1 className="font-display text-3xl text-hearth-600">Mathom</h1><h2 className="mt-4 font-display text-xl">Sign in</h2><form onSubmit={submit} className="mt-5 space-y-3 text-left"><label className="block text-sm">Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} className="mt-1 w-full rounded border p-2"/></label><label className="block text-sm">Password<input required type="password" value={password} onChange={e=>setPassword(e.target.value)} className="mt-1 w-full rounded border p-2"/></label>{error&&<p className="text-sm text-red-700">{error}</p>}<button disabled={busy} className="btn-primary w-full">{busy?'Signing in…':'Sign in'}</button></form>{status.authentik_configured&&<button onClick={login} className="mt-3 w-full rounded border p-2">Continue with Authentik</button>}</div></div>;
}
