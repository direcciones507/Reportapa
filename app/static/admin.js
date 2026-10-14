let csrf='',page=1,total=0,loadSequence=0;const message=document.querySelector('#message');
const ADMIN_IDLE_MS=15*60*1000;
let lastAdminActivity=Date.now(),adminIdleTimer=null;
function endAdminSession(){
 if(document.querySelector('#panel').hidden)return;
 document.querySelector('#panel').hidden=true;
 document.querySelector('#login').hidden=false;
 csrf='';
 message.textContent='La sesión se cerró por inactividad. Inicie sesión nuevamente.';
 fetch('/api/admin/logout',{method:'POST',headers:{'X-CSRF-Token':window.__adminIdleCsrf||''}}).catch(()=>{});
}
function checkAdminIdle(){
 if(!document.querySelector('#panel').hidden&&Date.now()-lastAdminActivity>=ADMIN_IDLE_MS)endAdminSession();
}
['pointerdown','keydown','touchstart','scroll'].forEach(eventName=>document.addEventListener(eventName,()=>{
 if(!document.querySelector('#panel').hidden)lastAdminActivity=Date.now();
},{passive:true}));
document.addEventListener('visibilitychange',checkAdminIdle);
window.addEventListener('focus',checkAdminIdle);
adminIdleTimer=setInterval(checkAdminIdle,10000);
function query(){return new URLSearchParams([...new FormData(document.querySelector('#filters'))].filter(([,v])=>v));}
async function api(url,options={}){const r=await fetch(url,{...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});const d=await r.json();if(!r.ok){if(r.status===401){document.querySelector('#panel').hidden=true;document.querySelector('#login').hidden=false;}throw Error(typeof d.detail==='string'?d.detail:'Solicitud inválida');}return d;}
function text(tag,value,parent){const el=document.createElement(tag);el.textContent=value;parent.append(el);return el;}
function renderStatistics(stats,at){
  const root=document.querySelector('#statistics');root.replaceChildren();
  text('h2','Informe de los reportes seleccionados',root);
  text('p','Actualizado: '+new Date(at).toLocaleString('es-PA',{timeZone:'America/Panama'}),root);
  const totals=document.createElement('dl');totals.className='stat-totals';root.append(totals);
  [['Reportes',stats.reports],['Grupos familiares declarados',stats.family_groups],
   ['Pendientes',stats.tracking.pending],['En seguimiento',stats.tracking.followup],
   ['Con atención registrada',stats.tracking.attended],['Sin identificación familiar',stats.unidentified_family_reports],
   ['Viviendas únicas','No determinadas']].forEach(([label,value])=>{const item=document.createElement('div');totals.append(item);text('dt',label,item);text('dd',String(value),item);});
  text('p',stats.family_method,root);text('p',stats.attention_method,root);
  text('h3','Comunidades (todos los reportes filtrados)',root);
  const scroll=document.createElement('div');scroll.className='stat-scroll';root.append(scroll);
  const table=document.createElement('table');scroll.append(table);const head=document.createElement('thead');table.append(head);
  const titles=document.createElement('tr');head.append(titles);
  ['Provincia','Distrito','Corregimiento','Comunidad','Reportes','Pendientes','En seguimiento','Atención registrada','Daños registrados','Necesidades registradas','Consultar'].forEach(t=>text('th',t,titles).scope='col');
  const body=document.createElement('tbody');table.append(body);
  const counts=values=>Object.entries(values).map(([k,n])=>k+': '+n).join(', ');
  stats.communities.forEach(c=>{const tr=document.createElement('tr');body.append(tr);
    [...Object.values(c.location),c.reports,c.pending,c.followup,c.attended,counts(c.damages),counts(c.needs)].forEach(v=>text('td',String(v),tr));
    const cell=document.createElement('td');tr.append(cell);const button=text('button','Ver reportes',cell);button.type='button';
    button.onclick=()=>{const form=document.querySelector('#filters');Object.entries(c.location).forEach(([k,v])=>{form.elements.namedItem(k).value=v;});page=1;load();};
  });
  if(!stats.reports)text('p','No hay reportes con estos filtros. Puede cambiar el período o limpiar los filtros.',root);
  text('h3','Tipos de daños',root);const damageList=document.createElement('ul');root.append(damageList);
  stats.damages.forEach(d=>text('li',d.type+': '+d.reports+' reportes',damageList));
  text('h3','Necesidades declaradas',root);text('p',stats.needs_method,root);
  const needsList=document.createElement('ul');root.append(needsList);
  stats.needs.forEach(n=>text('li',n.category+': '+(n.family_groups===null?'No especificada':n.family_groups+' grupos familiares · '+n.reports+' reportes'+(n.unidentified_family_reports?' · '+n.unidentified_family_reports+' sin identificación familiar':'')),needsList));
}
async function load(){const sequence=++loadSequence;const output=document.querySelector('#statistics');output.replaceChildren();text('p','Consultando estadísticas de los filtros seleccionados…',output);try{const q=query();document.querySelectorAll('.export').forEach(a=>a.href='/api/admin/export/'+a.dataset.kind+'?'+q);q.set('page',page);q.set('include_statistics','true');const d=await api('/api/admin/reports?'+q);if(sequence!==loadSequence)return;renderStatistics(d.statistics,d.statistics_at);total=d.total;document.querySelector('#total').textContent=total+' reportes · página '+page;const root=document.querySelector('#reports');root.replaceChildren();d.reports.forEach(r=>{const a=document.createElement('article');root.append(a);text('h2',r.id+' · '+r.data.name,a);renderHousehold(r,a);text('p','Reporte realizado por: '+(r.data.reporter_name||r.data.name),a);text('p',new Date(r.created_at).toLocaleString('es-PA'),a);text('p',[r.data.province,r.data.district,r.data.township,r.data.community].join(' / '),a);text('p','Teléfono: '+r.data.phone,a);text('p',(r.data.damage_type||'No especificada')+' — '+(r.data.damage||''),a);text('p','Necesidades: '+(Array.isArray(r.data.needs)?r.data.needs:[]).filter(n=>typeof n==='string').join(', ')+' '+(r.data.needs_detail||''),a);const link=text('a','Abrir Google Maps',a);link.href=r.data.maps;link.target='_blank';link.rel='noopener noreferrer';r.photos.forEach(p=>{const img=document.createElement('img');img.src='/api/admin/reports/'+r.id+'/photos/'+p;img.alt='Fotografía privada del reporte';img.loading='lazy';a.append(img);});renderHelp(r,a);renderLifecycle(r,a);const l=text('label','Estado operativo del reporte',a),s=document.createElement('select');['pendiente','contactado','visitado'].forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.append(o);});s.value=r.status;l.append(s);s.addEventListener('change',async()=>{try{await api('/api/admin/reports/'+r.id,{method:'PATCH',body:JSON.stringify({status:s.value})});message.textContent='Estado guardado';await load();}catch(e){s.value=r.status;message.textContent=e.message;}});});document.querySelector('#prev').disabled=page===1;document.querySelector('#next').disabled=page*20>=total;}catch(e){if(sequence!==loadSequence)return;output.replaceChildren();text('p','No se pudieron actualizar las estadísticas. Vuelva a aplicar los filtros.',output);message.textContent=e.message;}}
async function refreshStorage(){const output=document.querySelector('#storage-metrics');try{const d=await api('/api/admin/storage');const gb=n=>(n/1024**3).toFixed(2)+' GiB';output.textContent='Reportes totales: '+d.total_reports+' · '+(d.storage_available?'Fotografías almacenadas: '+d.photographs+' · Volumen utilizado: '+gb(d.used_bytes)+' · Disponible: '+gb(d.available_bytes)+' · Ocupación: '+d.occupation_percent+' %'+(d.alert?' · ALERTA '+d.alert+' %':''):'Almacenamiento de fotografías temporalmente indisponible. Los reportes pueden continuar sin foto.');}catch(e){output.textContent='No se pudieron consultar los indicadores. Vuelva a actualizar.';}}
document.querySelector('#refresh-storage').onclick=refreshStorage;
async function opened(token){csrf=token;window.__adminIdleCsrf=token;lastAdminActivity=Date.now();document.querySelector('#login').hidden=true;document.querySelector('#panel').hidden=false;await load();await refreshStorage();await loadAid().catch(e=>message.textContent=e.message);}
document.querySelector('#login').addEventListener('submit',async e=>{e.preventDefault();try{const r=await api('/api/admin/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});e.target.reset();message.textContent='';await opened(r.csrf);}catch(e){message.textContent=e.message;}});
document.querySelector('#filters').addEventListener('submit',e=>{e.preventDefault();page=1;load();});
document.querySelector('#reset-filters').onclick=()=>{document.querySelector('#filters').reset();page=1;load();};
document.querySelector('#prev').onclick=()=>{page--;load();};document.querySelector('#next').onclick=()=>{page++;load();};document.querySelector('#logout').onclick=async()=>{try{await api('/api/admin/logout',{method:'POST'});location.reload();}catch(e){message.textContent=e.message;}};
fetch('/api/config').then(r=>r.json()).then(c=>[...c.needs,'No especificada'].forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;document.querySelector('[name=need]').append(o);}));api('/api/admin/session').then(r=>opened(r.csrf)).catch(()=>{});

function renderHelp(r,parent){
  const box=document.createElement('section');box.className='report-followup';parent.append(box);
  const heading=text('h3','Ayuda: '+ReportaFollowup.states[r.estado_ayuda],box);
  if(['pendiente_confirmar','sin_ayuda'].includes(r.estado_ayuda))heading.className='help-attention';
  text('p','Último seguimiento: '+(r.ayuda_actualizada_at?new Date(r.ayuda_actualizada_at).toLocaleString('es-PA'):'Sin confirmar'),box);
  const actions=document.createElement('div');actions.className='report-followup-actions';box.append(actions);
  const wa=text('button','Consultar ayuda por WhatsApp',actions);wa.type='button';
  wa.onclick=()=>{try{const url=ReportaFollowup.whatsappUrl(r.data.phone,r.id);window.open(url,'_blank','noopener,noreferrer');text('p','Revise el mensaje en WhatsApp y envíelo manualmente. Abrir WhatsApp no confirma el envío ni cambia el estado de ayuda.',box);}catch(e){message.textContent=e.message;}};
  const pdf=text('a','Descargar ficha PDF individual',actions);pdf.href='/api/admin/reports/'+encodeURIComponent(r.id)+'/pdf';pdf.className='button';
  const label=text('label','Estado de ayuda',box),select=document.createElement('select');
  Object.entries(ReportaFollowup.states).forEach(([value,title])=>{const o=document.createElement('option');o.value=value;o.textContent=title;select.append(o);});select.value=r.estado_ayuda;label.append(select);
  const noteLabel=text('label','Observación breve (opcional)',box),note=document.createElement('textarea');note.maxLength=500;note.value=r.ayuda_observacion||'';noteLabel.append(note);
  const save=text('button','Guardar seguimiento de ayuda',box);save.type='button';
  save.onclick=async()=>{save.disabled=true;try{await api('/api/admin/reports/'+r.id,{method:'PATCH',body:JSON.stringify({estado_ayuda:select.value,observacion:note.value})});message.textContent='Seguimiento guardado';await load();}catch(e){message.textContent=e.message;}finally{save.disabled=false;}};
  if(r.ayuda_historial?.length){const details=document.createElement('details');box.append(details);text('summary','Historial de seguimiento',details);r.ayuda_historial.slice().reverse().forEach(h=>text('p',new Date(h.fecha).toLocaleString('es-PA')+' · '+ReportaFollowup.states[h.estado]+(h.observacion?' · '+h.observacion:''),details));}
}

function renderHousehold(r,parent){
  text('p','Familia: '+(r.data.family_name||'Sin informar')+' · Personas afectadas: '+(r.data.total_people??'Sin informar'),parent);
  const labels={age_0_5:'0 a 5 años',age_6_17:'6 a 17 años',age_18_59:'18 a 59 años',age_60_plus:'60 años o más',people_disability:'Personas con discapacidad'};
  text('p',Object.entries(labels).filter(([key])=>key==='people_disability'||r.data[key]>0).map(([key,label])=>label+': '+(r.data[key]??'Sin informar')).join(' · '),parent);
  if(r.data.coordinates)text('p','Coordenadas indicadas en Maps: '+r.data.coordinates.latitude+', '+r.data.coordinates.longitude,parent);
}
function renderLifecycle(r,parent){
  const section=document.createElement('section');section.className='report-management';parent.append(section);
  text('h3',r.archived_at?'Reporte archivado':'Gestión del reporte',section);
  if(r.archived_at)text('p','Archivado el '+new Date(r.archived_at).toLocaleString('es-PA')+'. Se conservan los datos y fotografías.',section);
  const archive=text('button',r.archived_at?'Restaurar del archivo':'Archivar reporte',section);archive.type='button';
  archive.onclick=async()=>{archive.disabled=true;try{await api('/api/admin/reports/'+r.id,{method:'PATCH',body:JSON.stringify({archived:!r.archived_at})});message.textContent=r.archived_at?'Reporte restaurado':'Reporte archivado sin borrar datos';await load();}catch(e){message.textContent=e.message;}finally{archive.disabled=false;}};
  const details=document.createElement('details');section.append(details);text('summary','Eliminación definitiva',details);
  text('p','Eliminar borra los datos y fotos del sistema activo. Los respaldos anteriores vencen según la política de conservación. Esta acción no se puede deshacer.',details);
  const label=text('label','Escriba ELIMINAR '+r.id+' para confirmar',details),confirm=document.createElement('input');confirm.autocomplete='off';label.append(confirm);
  const remove=text('button','Eliminar definitivamente',details);remove.type='button';remove.className='danger';
  remove.onclick=async()=>{if(confirm.value!=='ELIMINAR '+r.id){message.textContent='La confirmación no coincide con el número de reporte';return;}remove.disabled=true;try{const result=await api('/api/admin/reports/'+r.id,{method:'DELETE',body:JSON.stringify({confirm:confirm.value})});await load();message.textContent=result.message;}catch(e){message.textContent=e.message;}finally{remove.disabled=false;}};
}

async function loadAid(){
 const workers=await api('/api/admin/aid/workers');
 const workerRoot=document.querySelector('#aid-workers');workerRoot.replaceChildren();
 workers.workers.filter(w=>w.active).forEach(w=>{
  const row=document.createElement('div');row.className='aid-worker-row';workerRoot.append(row);
  text('span',w.full_name+' · Activo',row).className='aid-worker-identity';
  if(w.active){
   const actions=document.createElement('div');actions.className='aid-worker-actions';row.append(actions);
   const reset=text('button','Restablecer código',actions);reset.type='button';
   reset.onclick=async()=>{
    if(!confirm('¿Generar un nuevo código de seis números para '+w.full_name+'? El anterior dejará de funcionar.'))return;
    reset.disabled=true;
    try{
     const result=await api('/api/admin/aid/workers/'+encodeURIComponent(w.id)+'/reset-code',{method:'POST'});
     document.querySelector('#aid-issued-code').textContent='Nuevo código de '+result.full_name+': '+result.code+' (guárdelo ahora; no se volverá a mostrar)';
    }catch(e){message.textContent=e.message;}finally{reset.disabled=false;}
   };
   const button=text('button','Revocar acceso',actions);button.type='button';
   button.onclick=async()=>{
    if(!confirm('¿Revocar acceso de '+w.full_name+'?'))return;
    button.disabled=true;reset.disabled=true;
    try{await api('/api/admin/aid/workers/'+encodeURIComponent(w.id)+'/revoke',{method:'POST'});row.remove();await loadAid();}
    catch(e){message.textContent=e.message;button.disabled=false;reset.disabled=false;}
   };
  }
 });
 const deliveries=await api('/api/admin/aid/deliveries');
 const root=document.querySelector('#aid-deliveries');root.replaceChildren();
 text('p',deliveries.deliveries.length+' entregas recientes',root);
 deliveries.deliveries.forEach(d=>{
  const row=document.createElement('article');root.append(row);
  text('h3',d.beneficiary_name+' · '+d.beneficiary_id,row);
  text('p',d.place+' · '+d.aid_type,row);
  text('p','Responsable: '+d.worker_name+' · '+new Date(d.created_at).toLocaleString('es-PA',{timeZone:'America/Panama'}),row);
 });
}
if (typeof document.querySelector === 'function') {
document.querySelector('#aid-create-worker').addEventListener('submit',async event=>{
 event.preventDefault();
 try{
  const data=Object.fromEntries(new FormData(event.target));
  const result=await api('/api/admin/aid/workers',{method:'POST',body:JSON.stringify(data)});
  event.target.reset();
  document.querySelector('#aid-issued-code').textContent='Código personal de '+result.full_name+': '+result.code+' (copiar ahora; no se volverá a mostrar)';
  await loadAid();
 }catch(e){message.textContent=e.message;}
});
document.querySelector('#aid-show-create').onclick=()=>{
 const form=document.querySelector('#aid-create-worker'),button=document.querySelector('#aid-show-create');
 form.hidden=!form.hidden;button.setAttribute('aria-expanded',String(!form.hidden));
};
document.querySelector('#aid-show-workers').onclick=async()=>{
 const list=document.querySelector('#aid-worker-list'),button=document.querySelector('#aid-show-workers');
 list.hidden=!list.hidden;button.setAttribute('aria-expanded',String(!list.hidden));
 if(!list.hidden)await loadAid().catch(e=>message.textContent=e.message);
};
document.querySelector('#aid-refresh').onclick=()=>loadAid().catch(e=>message.textContent=e.message);
}
