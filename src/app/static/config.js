'use strict';
const form=document.querySelector('#config-form');
const notice=document.querySelector('#notice');
const save=document.querySelector('#save');
let revision=null,busy=false;
const csrf=document.querySelector('meta[name="csrf-token"]').content;
function show(text,kind=''){notice.textContent=text;notice.className='notice '+kind;}
async function api(path,options={}){
 const response=await fetch(path,{...options,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...(options.headers||{})}});
 if(response.status===401){location.assign('/login');throw new Error('Bitte erneut anmelden.');}
 const data=await response.json();
 if(!data.ok)throw new Error(data.message||'Die Anfrage konnte nicht abgeschlossen werden.');
 return data;
}
function clearTokens(){document.querySelectorAll('[data-secret]').forEach(input=>{input.value='';input.type='password';});document.querySelectorAll('[data-reveal]').forEach(button=>button.textContent='Anzeigen');document.querySelectorAll('[data-clear]').forEach(input=>input.checked=false);}
function controls(disabled){busy=disabled;save.disabled=disabled||!revision;document.querySelector('#reload').disabled=disabled;form.querySelectorAll('input,[data-reveal]').forEach(input=>{const clear=input.dataset.secret&&document.querySelector('[data-clear="'+input.dataset.secret+'"]');input.disabled=disabled||Boolean(clear&&clear.checked);});}
async function load(quiet=false){
 controls(true);
 try{
  const data=await api('/api/overview');revision=data.revision;
  for(const [name,value]of Object.entries(data.public)){const input=form.elements.namedItem(name);if(input)input.value=value;}
  clearTokens();
  for(const key of ['telegram','discord','openai']){const badge=document.querySelector('#state-'+key);badge.textContent=data.configured[key]?'Eingerichtet':'Nicht eingerichtet';badge.classList.toggle('configured',data.configured[key]);}
  const health=data.configured.hc_bot||data.configured.hc_server;document.querySelector('#state-health').textContent=health?'Eingerichtet':'Optional';document.querySelector('#state-health').classList.toggle('configured',health);
  if(data.busy&&data.job){await poll(data.job);return;}
  if(data.blocked){show('Eine frühere Änderung muss zuerst per SSH geprüft werden.','error');return;}
  if(!quiet)show('Konfiguration geladen. Gespeicherte Tokens bleiben verborgen.');
  controls(false);
 }catch(error){show(error.message,'error');controls(true);}
}
async function poll(job){
 controls(true);
 const stages={queued:'Änderung wird vorbereitet …',stopping:'Bisherige Konfiguration gesichert. Dienste werden kurz angehalten …',starting:'Neue Konfiguration wird geladen …',checking:'Verbindungen werden geprüft. Das kann bis zu drei Minuten dauern …',restoring:'Die bisherige Konfiguration wird wiederhergestellt …'};
 for(let count=0;count<400;count++){
  const data=await api('/api/jobs/'+encodeURIComponent(job));
  if(data.state==='success'){await load(true);show('Gespeichert. Die Dienste sind wieder bereit. Prüfe jetzt /status in Telegram und Discord.','success');return;}
  if(data.state==='rolled_back'){await load(true);show('Die neue Konfiguration konnte nicht vollständig gestartet werden. Die bisherigen Werte wurden wiederhergestellt.','error');return;}
  if(['failed','interrupted'].includes(data.state)){await load(true);show(data.message||'Änderung nicht übernommen. Bitte den Zustand prüfen.','error');return;}
  show(stages[data.state]||'Änderung wird verarbeitet …');
  await new Promise(resolve=>setTimeout(resolve,1500));
 }
 show('Die Verarbeitung dauert länger. Bitte die Seite neu laden, um den gespeicherten Vorgang abzufragen. Nicht erneut absenden.','error');
}
document.querySelectorAll('[data-reveal]').forEach(button=>button.addEventListener('click',()=>{const input=document.getElementById(button.dataset.reveal);input.type=input.type==='password'?'text':'password';button.textContent=input.type==='password'?'Anzeigen':'Verbergen';}));
document.querySelectorAll('[data-clear]').forEach(input=>input.addEventListener('change',()=>{const field=document.querySelector('[data-secret="'+input.dataset.clear+'"]');field.disabled=input.checked;if(input.checked)field.value='';}));
document.querySelector('#reload').addEventListener('click',()=>{if(!busy)load();});
form.addEventListener('submit',async event=>{
 event.preventDefault();if(busy||!revision)return;
 if(!window.confirm('Änderungen übernehmen? Die bisherigen Werte werden gesichert. Telegram und Discord sind beim Neuladen kurz nicht erreichbar.'))return;
 const payload={revision,public:{},secrets:{}};
 for(const key of ['telegram_users','discord_application','discord_users','discord_guild','discord_channel','raid_devices'])payload.public[key]=form.elements.namedItem(key).value.trim();
 document.querySelectorAll('[data-secret]').forEach(input=>{const key=input.dataset.secret,clear=document.querySelector('[data-clear="'+key+'"]');payload.secrets[key]=clear&&clear.checked?{mode:'clear'}:input.value.trim()?{mode:'replace',value:input.value.trim()}:{mode:'keep'};});
 controls(true);show('Eingaben werden geprüft …');
 try{
  const reply=await api('/api/config',{method:'POST',body:JSON.stringify(payload)});
  clearTokens();Object.values(payload.secrets).forEach(spec=>{if(spec.value)spec.value='';});
  if(reply.state==='unchanged'){controls(false);show('Keine Änderung erforderlich. Die vorhandenen Werte bleiben erhalten.','success');return;}
  await poll(reply.job);
 }catch(error){show(error.message+' Falls die Verbindung unterbrochen wurde, lade die Seite neu und prüfe den Vorgang vor einer Wiederholung.','error');controls(false);}
});
load();
