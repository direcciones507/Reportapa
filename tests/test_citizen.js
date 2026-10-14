const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function citizen(responses,files=[]){
  const nodes={},requests=[];let handler;
  const node=id=>nodes[id]??=( {hidden:false,textContent:'',value:'yes',addEventListener(){},append(){}} );
  const form=node('#report');form.elements={photos:{files}};form.reset=()=>{form.resets=(form.resets||0)+1;};form.addEventListener=(event,fn)=>handler=fn;
  class Data{constructor(){this.fields={};}append(k,v){this.fields[k]=v;}}
  const context={window:{location:{hash:'#report'},addEventListener(){}},document:{querySelector:node,createElement:()=>({append(){}}),createTextNode:v=>v},crypto:{randomUUID:()=>String(Math.random())},FormData:Data,fetch:async(url,options)=>{if(url==='/api/config')return {json:async()=>({enabled:true,notice:'',needs:[]})};requests.push(options.body.fields);const result=responses.shift();return {ok:result.ok,json:async()=>result.body};}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../app/static/citizen.js'),'utf8'),context);
  return {nodes,requests,send:()=>handler({preventDefault(){}})};
}
test('successful photo fallback displays number and exact warning without general error',async()=>{
  const warning='No se puede subir la foto en este momento, pero puedes seguir con tu reporte.';
  const page=citizen([{ok:true,body:{id:'RPA-00000001',photo_warning:warning}}],[{size:100}]);
  await page.send();assert.equal(page.nodes['#number'].textContent,'Número de reporte: RPA-00000001');
  assert.equal(page.nodes['#photo-warning'].textContent,warning);assert.equal(page.nodes['#photo-warning'].hidden,false);
  assert.equal(page.nodes['#message'].textContent,'');assert.equal(page.nodes['#success'].hidden,false);assert.equal(page.nodes['#report'].hidden,true);
});
test('temporary failure keeps idempotency key and allows successful no-photo retry',async()=>{
  const page=citizen([{ok:false,body:{detail:'Temporal'}},{ok:true,body:{id:'RPA-00000002'}}]);
  await page.send();assert.equal(page.nodes['#report'].resets,undefined);
  await page.send();assert.equal(page.requests[0].idempotency_key,page.requests[1].idempotency_key);
  assert.equal(page.nodes['#photo-warning'].hidden,true);assert.equal(page.nodes['#report'].resets,1);
});
test('multiple new photos are rejected before sending',async()=>{
  const page=citizen([],[{size:100},{size:100}]);await page.send();assert.equal(page.requests.length,0);
  assert.match(page.nodes['#message'].textContent,/una foto/);
});
