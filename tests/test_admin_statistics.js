const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/admin.js','utf8');
function view(){
  const elements=[];
  const element=tag=>{const e={tag,children:[],append(...n){this.children.push(...n);},replaceChildren(){this.children=[];}};elements.push(e);return e;};
  const root=element('section'),fields=Object.fromEntries(['province','district','township','community','date_from','need'].map(k=>[k,{value:''}]));
  fields.date_from.value='2026-10-11';fields.need.value='Agua potable';
  const context={document:{createElement:element,querySelector(s){return s==='#statistics'?root:{elements:{namedItem:k=>fields[k]}};}},Date,page:3,load(){context.loaded=true;}};
  vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function text('),source.indexOf('async function load(')),context);
  return {context,elements,root,fields};
}
test('statistics renders selected totals safely and drills into the full hierarchy, preserving other filters',()=>{
  const page=view(),stats={reports:27,family_groups:24,unidentified_family_reports:3,tracking:{pending:20,followup:5,attended:2},family_method:'Declaradas',attention_method:'Atención confirmada',needs_method:'Selección explícita',damages:[{type:'<script>private</script>',reports:1}],needs:[{category:'Alojamiento temporal',family_groups:null,reports:1}],communities:[{location:{province:'Veraguas',district:'Soná',township:'Soná',community:'El Centro'},reports:27,pending:20,followup:5,attended:2,damages:{Paredes:27},needs:{'Agua potable':27}}]};
  page.context.renderStatistics(stats,'2026-10-11T12:00:00Z');
  assert.equal(page.elements.filter(e=>e.tag==='dd')[0].textContent,'27');
  assert.ok(page.elements.some(e=>e.textContent==='<script>private</script>: 1 reportes'));
  assert.ok(page.elements.some(e=>e.tag==='td'&&e.textContent==='Alojamiento temporal'));
  assert.ok(page.elements.some(e=>e.tag==='td'&&e.textContent==='No determinados'));
  page.elements.find(e=>e.textContent==='Ver reportes').onclick();
  assert.equal(page.fields.community.value,'El Centro');assert.equal(page.fields.district.value,'Soná');
  assert.equal(page.fields.date_from.value,'2026-10-11');assert.equal(page.fields.need.value,'Agua potable');
  assert.equal(page.context.page,1);assert.equal(page.context.loaded,true);
  assert.ok(!source.includes('innerHTML'));
});
test('admin reports request statistics together with the selected page and export scope',()=>{
  assert.match(source,/q\.set\('include_statistics','true'\)/);
  assert.match(source,/sequence!==loadSequence/);
  assert.match(source,/Array\.isArray\(r\.data\.needs\)/); // Existing individual report rendering remains.
});
