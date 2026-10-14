const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const source=fs.readFileSync('app/static/admin.js','utf8');
const render=source.slice(source.indexOf('async function loadAid(){'),source.indexOf("\nif (typeof document.querySelector",source.indexOf('async function loadAid(){')));
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.disabled=false;}
 append(node){this.children.push(node);node.parent=this;if(!this.firstChild)this.firstChild=node;}
 replaceChildren(){this.children=[];}
 remove(){this.parent.children=this.parent.children.filter(n=>n!==this);}
}
function fixture(refreshFails=false){
 const root=new Element('div'),deliveries=new Element('div'),message={};let revoked=false;
 const doc={createElement:tag=>new Element(tag),querySelector:s=>({'#aid-workers':root,'#aid-deliveries':deliveries,'#aid-issued-code':new Element('p')}[s])};
 const text=(tag,value,parent)=>{const el=new Element(tag);el.textContent=value;parent.append(el);return el;};
 const calls=[];const api=async(url)=>{calls.push(url);if(url.endsWith('/revoke')){revoked=true;return {ok:true};}if(url.endsWith('/deliveries'))return {deliveries:[]};if(revoked&&refreshFails)throw Error('refresh failed');return {workers:[{id:'active',full_name:'Responsable activo',active:!revoked},{id:'retired',full_name:'Histórico revocado',active:false}]};};
 const load=new Function('document','api','text','confirm','message',render+';return loadAid;')(doc,api,text,()=>true,message);
 return {load,root,calls,message};
}
test('worker list shows only active records and retains the two action controls together',async()=>{
 const f=fixture();await f.load();assert.equal(f.root.children.length,1);const row=f.root.children[0];
 assert.equal(row.children[0].textContent,'Responsable activo · Activo');assert.equal(row.children[1].className,'aid-worker-actions');
 assert.deepEqual(row.children[1].children.map(b=>b.textContent),['Restablecer código','Revocar acceso']);
 await row.children[1].children[1].onclick();assert.equal(f.root.children.length,0);assert(f.calls.includes('/api/admin/aid/workers/active/revoke'));
});
test('successful revoke removes the row immediately even if the subsequent refresh fails',async()=>{
 const f=fixture(true);await f.load();await f.root.children[0].children[1].children[1].onclick();assert.equal(f.root.children.length,0);assert.equal(f.message.textContent,'refresh failed');
});
