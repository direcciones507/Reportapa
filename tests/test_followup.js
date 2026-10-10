const {test}=require('node:test');
const assert=require('node:assert/strict');
const {whatsappUrl,message,states}=require('../app/static/followup.js');
test('WhatsApp normalizes Panama phone and only includes number and prepared message',()=>{
  for(const phone of ['6123-4567','+507 6123 4567','(507) 61234567']){
    const url=new URL(whatsappUrl(phone));
    assert.equal(url.origin,'https://wa.me');assert.equal(url.pathname,'/50761234567');
    assert.equal(url.searchParams.get('text'),message);assert.equal([...url.searchParams].length,1);
  }
  assert.equal(new URL(whatsappUrl('+507 212-3456')).pathname,'/5072123456');
  assert.match(message,/¿Recibieron ayuda completa, ayuda parcial o todavía no han recibido\?/);
});
test('invalid phone never produces a WhatsApp URL',()=>{
  for(const phone of ['',null,'abc61234567','+1 6123456789','00000000','12345678','6123456','https://evil.test/61234567','61234567 ext 2'])assert.throws(()=>whatsappUrl(phone),/no es válido/);
});
test('four independent aid states',()=>assert.deepEqual(Object.keys(states),['pendiente_confirmar','sin_ayuda','parcial','completa']));

const fs=require('node:fs'),vm=require('node:vm');
function render(phone){
  const elements=[],calls=[];
  const create=tag=>({tag,children:[],append(...nodes){this.children.push(...nodes);}});
  const context={document:{createElement(tag){const e=create(tag);elements.push(e);return e;}},ReportaFollowup:require('../app/static/followup.js'),message:{textContent:''},window:{open(...args){calls.push(args);}},api(){throw Error('Opening WhatsApp must not change server state');},text(tag,value,parent){const e=create(tag);e.textContent=value;elements.push(e);parent.append(e);return e;}};
  const source=fs.readFileSync(require.resolve('../app/static/admin.js'),'utf8');
  vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function renderHelp')),context);
  context.renderHelp({id:'RPA-00000001',data:{phone},estado_ayuda:'pendiente_confirmar',ayuda_observacion:'',ayuda_historial:[]},create('article'));
  return {context,elements,calls,button:elements.find(e=>e.textContent==='Consultar ayuda por WhatsApp')};
}
test('admin button opens composer only on explicit click and never updates report',()=>{
  const page=render('+507 6123-4567');assert.equal(page.calls.length,0);
  page.button.onclick();assert.equal(page.calls.length,1);assert.equal(page.calls[0][0],whatsappUrl('61234567'));
  assert.equal(page.calls[0][2],'noopener,noreferrer');assert.equal(page.context.message.textContent,'');
});
test('admin button reports invalid phone without opening external site',()=>{
  const page=render('invalid');page.button.onclick();assert.equal(page.calls.length,0);assert.match(page.context.message.textContent,/teléfono registrado no es válido/);
});
