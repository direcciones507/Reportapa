let csrf='',key=crypto.randomUUID();
const login=document.querySelector('#aid-login'),panel=document.querySelector('#aid-panel'),form=document.querySelector('#aid-form'),message=document.querySelector('#aid-message');
async function api(url,options={}){
 const response=await fetch(url,{...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});
 const data=await response.json();
 if(!response.ok)throw Error(data.detail||'No se pudo completar');
 return data;
}
function opened(data){csrf=data.csrf;login.hidden=true;panel.hidden=false;document.querySelector('#worker').textContent='Responsable: '+data.full_name;}
login.addEventListener('submit',async event=>{
 event.preventDefault();message.textContent='';
 try{
  const values=Object.fromEntries(new FormData(login));
  const result=await api('/api/aid/login',{method:'POST',body:JSON.stringify(values)});
  login.reset();opened({csrf:result.csrf,full_name:values.full_name});
 }catch(error){message.textContent=error.message;}
});
form.addEventListener('submit',async event=>{
 event.preventDefault();
 const button=document.querySelector('#aid-save');button.disabled=true;
 try{
  const values={...Object.fromEntries(new FormData(form)),idempotency_key:key};
  const result=await api('/api/aid/deliveries',{method:'POST',body:JSON.stringify(values)});
  message.textContent='Entrega guardada. Registro: '+result.id;
  form.reset();key=crypto.randomUUID();
 }catch(error){message.textContent=error.message;}
 finally{button.disabled=false;}
});
document.querySelector('#aid-logout').onclick=async()=>{
 try{await api('/api/aid/logout',{method:'POST'});location.reload();}
 catch(error){message.textContent=error.message;}
};
api('/api/aid/session').then(opened).catch(()=>{});
