const {test}=require('node:test');
const assert=require('node:assert/strict');
const {whatsappUrl,states}=require('../app/static/followup.js');
const expected=id=>'Hola, le escribimos de ReportaPA para dar seguimiento a su situación.\n\nNúmero de reporte: '+id+'\n\n¿Nos puede confirmar si ya recibió ayuda?\n\nGracias por su respuesta.';
test('WhatsApp normalizes Panama phone and only includes number and prepared message',()=>{
  for(const phone of ['6123-4567','+507 6123 4567','(507) 61234567']){
    const url=new URL(whatsappUrl(phone,'RPA-00000001'));
    assert.equal(url.origin,'https://wa.me');assert.equal(url.pathname,'/50761234567');
    assert.equal(url.searchParams.get('text'),expected('RPA-00000001'));assert.equal([...url.searchParams].length,1);
  }
  assert.equal(new URL(whatsappUrl('+507 212-3456','RPA-00000001')).pathname,'/5072123456');
});
test('invalid phone never produces a WhatsApp URL',()=>{
  for(const phone of ['',null,'abc61234567','+1 6123456789','00000000','12345678','6123456','https://evil.test/61234567','61234567 ext 2'])assert.throws(()=>whatsappUrl(phone,'RPA-00000001'),/no es válido/);
});
test('four independent aid states',()=>assert.deepEqual(Object.keys(states),['pendiente_confirmar','sin_ayuda','parcial','completa']));

const fs=require('node:fs'),vm=require('node:vm');
function render(phone,id='RPA-00000001'){
  const elements=[],calls=[];
  const create=tag=>({tag,children:[],append(...nodes){this.children.push(...nodes);}});
  const context={document:{createElement(tag){const e=create(tag);elements.push(e);return e;}},ReportaFollowup:require('../app/static/followup.js'),message:{textContent:''},window:{open(...args){calls.push(args);}},api(){throw Error('Opening WhatsApp must not change server state');},text(tag,value,parent){const e=create(tag);e.textContent=value;elements.push(e);parent.append(e);return e;}};
  const source=fs.readFileSync(require.resolve('../app/static/admin.js'),'utf8');
  vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function renderHelp')),context);
  context.renderHelp({id,data:{phone},estado_ayuda:'pendiente_confirmar',ayuda_observacion:'',ayuda_historial:[]},create('article'));
  return {context,elements,calls,button:elements.find(e=>e.textContent==='Consultar ayuda por WhatsApp')};
}
test('admin button opens composer only on explicit click and never updates report',()=>{
  const page=render('+507 6123-4567');assert.equal(page.calls.length,0);
  page.button.onclick();assert.equal(page.calls.length,1);assert.equal(page.calls[0][0],whatsappUrl('61234567','RPA-00000001'));
  assert.equal(page.calls[0][2],'noopener,noreferrer');assert.equal(page.context.message.textContent,'');
});
test('admin button reports invalid phone without opening external site',()=>{
  const page=render('invalid');page.button.onclick();assert.equal(page.calls.length,0);assert.match(page.context.message.textContent,/teléfono registrado no es válido/);
});

test('permanent erasure requires exact report confirmation before making a request',async()=>{
  const page=render('61234567');const requests=[];
  page.context.api=async(url,options)=>{requests.push({url,options});return {message:'Datos eliminados'};};page.context.load=async()=>{};
  page.context.renderLifecycle({id:'RPA-00000001',archived_at:null},{append(){}});
  const button=page.elements.find(e=>e.textContent==='Eliminar definitivamente');const input=page.elements.find(e=>e.tag==='input');
  input.value='ELIMINAR RPA-OTRO';await button.onclick();assert.equal(requests.length,0);assert.match(page.context.message.textContent,/confirmación no coincide/);
  input.value='ELIMINAR RPA-00000001';await button.onclick();assert.equal(requests.length,1);
  assert.equal(requests[0].options.method,'DELETE');assert.deepEqual(JSON.parse(requests[0].options.body),{confirm:'ELIMINAR RPA-00000001'});
});
test('archive button uses the same private report route and preserves operational state',async()=>{
  const page=render('61234567');const requests=[];
  page.context.api=async(url,options)=>{requests.push({url,options});return {ok:true};};page.context.load=async()=>{};
  page.context.renderLifecycle({id:'RPA-00000001',archived_at:null,status:'visitado'},{append(){}});
  await page.elements.find(e=>e.textContent==='Archivar reporte').onclick();
  assert.equal(requests[0].options.method,'PATCH');assert.deepEqual(JSON.parse(requests[0].options.body),{archived:true});
});

test('each selected report supplies its own number and preserves its recipient',()=>{
  const reports=[{id:'RPA-00000001',phone:'61234567'},{id:'RPA-00000234',phone:'69876543'}];
  const prepared=[];
  for(const report of reports){
    const page=render(report.phone,report.id);page.button.onclick();
    assert.equal(page.calls.length,1);
    const url=new URL(page.calls[0][0]);assert.equal(url.pathname,'/507'+report.phone);
    assert.equal(url.searchParams.get('text'),expected(report.id));
    prepared.push(url.searchParams.get('text'));
  }
  assert.notEqual(prepared[0],prepared[1]);
});
test('missing or malformed report number never prepares an unidentified message',()=>{
  for(const id of [undefined,null,'','RPA-undefined','another report'])assert.throws(()=>whatsappUrl('61234567',id),/número de reporte no es válido/);
});
