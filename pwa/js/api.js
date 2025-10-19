// js/api.js
const API_BASE = 'http://${window.location.hostname}:8000/api'; // REPLACE


async function authFetch(path, options={}){
const token = localStorage.getItem('access');
const headers = options.headers||{};
headers['Content-Type'] = headers['Content-Type'] || 'application/json';
if (token) headers['Authorization'] = `Bearer ${token}`;
const res = await fetch(`${API_BASE}${path}`, {...options, headers});
if (res.status === 401){
// Try silent refresh
const ok = await tryRefresh();
if (ok) return authFetch(path, options);
logout();
throw new Error('Unauthorized');
}
return res.ok ? await res.json() : null;
}


// Auth endpoints (existing)
async function requestOtp(phone){
const res = await fetch(`${API_BASE}/auth/request-otp/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone})});
return res.ok;
}
async function verifyOtp(phone, code){
const res = await fetch(`${API_BASE}/auth/verify-otp/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone,code})});
if (!res.ok) return false;
const data = await res.json();
localStorage.setItem('access', data.access);
localStorage.setItem('refresh', data.refresh);
localStorage.setItem('user', JSON.stringify(data.user));
// Register FCM token if available
if (window.registerForPush) window.registerForPush();
return true;
}


// Token refresh (simple)
async function tryRefresh(){
const refresh = localStorage.getItem('refresh');
if (!refresh) return false;
try {
const res = await fetch(`${API_BASE}/auth/token/refresh/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh})});
if (!res.ok) return false;
const data = await res.json();
localStorage.setItem('access', data.access);
return true;
} catch { return false; }
}


function logout(){
const token = localStorage.getItem('access');
}