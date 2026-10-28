'use strict';
const discovery={catalog:null,category:'pokemon',matches:[],selected:null,busy:false,token:0,controller:null};
function discoveryItem(id){if(!discovery.catalog)return null;for(const group of Object.values(discovery.catalog.categories)){const found=group.items.find(item=>item.id===id);if(found)return found;}return null;}
async function initDiscovery(){try{discovery.catalog=await(await api('/influencer/discovery')).json();renderDiscovery();renderSelectionSummary();}catch(e){$('discovery-status').textContent=e.message;}}
function discoveryReferenceChanged(){discovery.token++;discovery.controller?.abort();discovery.busy=false;discovery.matches=[];discovery.selected=null;state.inspirationId='';$('discovery-status').textContent='';renderDiscovery();}
function discoveryCard(item,rank=null){
 const button=document.createElement('button');button.type='button';button.className='discovery-character';button.dataset.inspiration=item.id;button.setAttribute('aria-label','Elegir '+item.name);button.setAttribute('aria-pressed',String(discovery.selected===item.id));
 if(item.image){const img=document.createElement('img');img.src=item.image;img.alt=item.name+' · referencia del personaje';img.loading='lazy';button.append(img);}else{const symbol=document.createElement('span');symbol.className='zodiac-symbol';symbol.textContent=item.symbol;button.append(symbol);}
 if(rank){const badge=document.createElement('small');badge.className='discovery-rank';badge.textContent=rank===1?'Mayor semejanza':'Alternativa '+rank;button.append(badge);}
 const name=document.createElement('strong');name.textContent=item.name;const text=document.createElement('span');text.className='discovery-character-summary';text.textContent=item.summary;button.append(name,text);
 button.onclick=()=>{discovery.selected=item.id;renderDiscovery();$('discovery-selected').scrollIntoView({behavior:'smooth',block:'nearest'});};return button;
}
function renderDiscovery(){
 if(!$('discovery-view'))return;
 const loaded=Boolean(state.file);$('discovery-photo').hidden=!loaded;$('discovery-upload-label').hidden=loaded;$('discovery-clear').hidden=!loaded;if(loaded)$('discovery-photo').src=$('reference-preview').src;
 $('discovery-analyze').disabled=!loaded||discovery.busy||!discovery.catalog?.matcher_ready;
 $('discovery-analyze').textContent=discovery.busy?'Buscando tu afinidad…':'Encontrar mi personaje ✦';
 if(!discovery.catalog)return;
 const universes=$('discovery-universes');universes.replaceChildren();
 for(const [id,group] of Object.entries(discovery.catalog.categories)){const button=document.createElement('button');button.type='button';button.dataset.universe=id;button.setAttribute('aria-pressed',String(id===discovery.category));const symbol=document.createElement('b');symbol.textContent=group.symbol;const name=document.createElement('strong');name.textContent=group.label;button.append(symbol,name);button.onclick=()=>{if(discovery.category===id)return;discovery.token++;discovery.controller?.abort();discovery.busy=false;discovery.category=id;$('discovery-finish').value=id==='zodiac'?'fantasy':'cinema';discovery.matches=[];discovery.selected=null;$('discovery-search').value='';$('discovery-status').textContent='';renderDiscovery();};universes.append(button);}
 const category=discovery.catalog.categories[discovery.category];$('discovery-title').textContent=discovery.category==='pokemon'?'¿Cuál es tu Pokémon?':discovery.category==='digimon'?'¿Cuál es tu Digimon?':'Tu guardián del Zodiaco';$('discovery-category-description').textContent=discovery.category==='zodiac'?category.description:category.items.length+' personajes para comparar con tu foto.';
 if(!discovery.catalog.matcher_ready)$('discovery-status').textContent='El reconocimiento visual no está instalado en este equipo. Puedes elegir un personaje abajo.';
 $('discovery-results-section').hidden=!discovery.matches.length;const results=$('discovery-results');results.replaceChildren();for(const item of discovery.matches)results.append(discoveryCard(item,item.rank));
 const search=$('discovery-search').value.trim().toLocaleLowerCase('es');const catalog=$('discovery-catalog');catalog.replaceChildren();for(const item of category.items.filter(item=>item.name.toLocaleLowerCase('es').includes(search)))catalog.append(discoveryCard(item));
 const selected=discoveryItem(discovery.selected);$('discovery-selected').hidden=!selected;
 if(selected){$('discovery-selected-name').textContent=selected.name+' · '+category.label;$('discovery-selected-summary').textContent=selected.summary;}
 $('discovery-transform').disabled=!loaded||!selected||state.posting||!Object.values(state.config?.models||{}).some(model=>model.ready);
}
async function runDiscovery(){
 if(!state.file||discovery.busy)return;
 const token=++discovery.token;const referenceVersion=state.referenceVersion;const category=discovery.category;
 discovery.controller?.abort();discovery.controller=new AbortController();discovery.busy=true;$('discovery-status').textContent='Comparando tu foto con este universo…';renderDiscovery();
 try{const form=new FormData();form.append('file',state.file);form.append('category',category);const result=await(await api('/influencer/discovery/match',{method:'POST',body:form,signal:discovery.controller.signal})).json();if(token!==discovery.token||referenceVersion!==state.referenceVersion||category!==discovery.category)return;discovery.matches=result.suggestions;discovery.selected=result.assigned_character?.id||result.suggestions[0]?.id||null;$('discovery-status').textContent=category==='zodiac'?'Estas son tus afinidades visuales de fantasía.':'Personaje asignado por semejanza visual: '+(discoveryItem(discovery.selected)?.name||'sin coincidencia')+'. Tu foto original se conserva.';}
 catch(e){if(e.name!=='AbortError'&&token===discovery.token)$('discovery-status').textContent=e.message;}
 finally{if(token===discovery.token){discovery.busy=false;renderDiscovery();}}
}
$('discovery-upload').onclick=()=>$('reference-input').click();$('discovery-camera').onclick=()=>$('camera-open').click();$('discovery-demo').onclick=()=>$('demo-input').click();$('discovery-clear').onclick=()=>$('reference-clear').click();$('discovery-analyze').onclick=runDiscovery;$('discovery-search').oninput=renderDiscovery;
for(const name of ['dragenter','dragover'])$('discovery-upload').addEventListener(name,e=>{e.preventDefault();$('discovery-upload').classList.add('dragging');});
for(const name of ['dragleave','drop'])$('discovery-upload').addEventListener(name,e=>{e.preventDefault();$('discovery-upload').classList.remove('dragging');if(name==='drop'&&e.dataTransfer.files[0])setFile(e.dataTransfer.files[0]);});
$('discover-another').onclick=()=>{history.replaceState(null,'','/studio?view=discovery');showView('discovery');};
$('discovery-transform').onclick=()=>{
 const item=discoveryItem(discovery.selected);if(!item||!state.file||state.posting)return;
 if(state.config.models.flux_klein?.ready)chooseModel('flux_klein');
 chooseCharacterType('natural',false);chooseStyle($('discovery-finish').value,false);
 state.inspirationId=item.id;$('custom-prompt').value='Conviérteme en una criatura humanoide inspirada en '+item.name+', conservando algunos rasgos de mi foto.';$('prompt-counter').textContent=$('custom-prompt').value.length+'/500';resetAttempt();renderSelectionSummary();
 showView('explore');$('generate').click();
};
