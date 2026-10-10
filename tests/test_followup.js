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
