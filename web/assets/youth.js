'use strict';
function youthModel(){return ['flux_klein','qwen_edit'].find(id=>state.config?.models?.[id]?.ready);}
function renderYouth(){
 if(!$('youth-view'))return;
 const loaded=Boolean(state.file);$('youth-photo').hidden=!loaded;$('youth-upload-label').hidden=loaded;$('youth-clear').hidden=!loaded;
 if(loaded)$('youth-photo').src=$('reference-preview').src;
 $('youth-generate').disabled=!loaded||!youthModel()||state.posting;
 $('youth-generate').textContent=state.posting?'Preparando tu retrato…':'Crear mi versión joven ✦';
 $('youth-status').textContent=!state.config?'Conectando con el estudio…':!youthModel()?'Se necesita FLUX o Qwen disponible para editar tu fotografía.':!loaded?'Sube una foto o usa la cámara para empezar.':'Se creará un retrato a los '+$('youth-age').value+' años. Podrás ver el progreso y comparar con tu original.';
}
$('youth-upload').onclick=()=>$('reference-input').click();
$('youth-camera').onclick=()=>$('camera-open').click();
$('youth-demo').onclick=()=>$('demo-input').click();
$('youth-clear').onclick=()=>$('reference-clear').click();
$('youth-age').onchange=()=>{resetAttempt();renderYouth();};
$('youth-generate').onclick=()=>{
 if(!state.file||state.posting)return;
 const model=youthModel();if(!model){renderYouth();return;}
 chooseModel(model,'square');chooseCharacterType('natural',false);chooseStyle('editorial',false);restoreAppearance({});
 state.inspirationId='';state.targetAge=Number($('youth-age').value);$('custom-prompt').value='';$('prompt-counter').textContent='0/500';
 $('identity').value='0.9';$('identity-value').textContent='0.90';
 generate();
};
