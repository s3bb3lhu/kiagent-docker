'use strict';
(()=>{
const choices={design:['redline','carbon','pulse'],color:['red','green','blue','royal','purple','darkpurple','anthracite'],logo:['brackets','cubes','power'],button:['solid','outline','split'],density:['comfortable','compact'],theme:['light','dark']};
const defaults={design:'carbon',color:'red',logo:'brackets',button:'split',density:'comfortable',theme:window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'};
let state={...defaults};
try{const saved=JSON.parse(localStorage.getItem('services-ui-v1')||'{}');for(const key of Object.keys(choices))if(choices[key].includes(saved[key]))state[key]=saved[key];if(!saved.theme&&['dark','light'].includes(localStorage.getItem('services-theme')))state.theme=localStorage.getItem('services-theme');}catch{}
function apply(){for(const [key,value] of Object.entries(state))document.documentElement.dataset[key]=value;document.documentElement.classList.remove('dark');}
function save(){apply();try{localStorage.setItem('services-ui-v1',JSON.stringify(state));}catch{}sync();}
function sync(){for(const key of Object.keys(choices)){const input=document.getElementById('ui-'+key);if(input)input.value=state[key];}const toggle=document.getElementById('theme');if(toggle){toggle.checked=state.theme==='dark';toggle.setAttribute('aria-label',toggle.checked?'Nachtmodus aktiv. Zum Tagmodus wechseln.':'Tagmodus aktiv. Zum Nachtmodus wechseln.');}const mode=document.getElementById('theme-label');if(mode)mode.textContent=state.theme==='dark'?'Nacht':'Tag';}
apply();
document.addEventListener('DOMContentLoaded',()=>{
for(const key of Object.keys(choices)){const input=document.getElementById('ui-'+key);if(input)input.addEventListener('change',()=>{if(choices[key].includes(input.value)){state[key]=input.value;save();}});}
const toggle=document.getElementById('theme');if(toggle)toggle.addEventListener('change',()=>{state.theme=toggle.checked?'dark':'light';save();});
const reset=document.getElementById('ui-reset');if(reset)reset.addEventListener('click',()=>{state={...defaults};save();});
document.addEventListener('click',event=>{const panel=document.getElementById('design-menu');if(panel?.open&&!panel.contains(event.target))panel.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){const panel=document.getElementById('design-menu');if(panel?.open){panel.open=false;panel.querySelector('summary').focus();}}});
sync();});
})();
