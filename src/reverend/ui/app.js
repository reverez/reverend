'use strict';
const $ = s => document.querySelector(s);
const token = $('meta[name="reverend-token"]').content;
const md = window.markdownit({html:false,linkify:true}).disable('image');
// Preserve escaped TeX delimiters through Markdown's escape processing.
md.inline.ruler.before('escape','tex_delimiters',(parser,silent)=>{
 const opening=parser.src.slice(parser.pos,parser.pos+2);
 if(!['\\(','\\['].includes(opening))return false;
 const closing=opening==='\\('? '\\)' : '\\]';
 const end=parser.src.indexOf(closing,parser.pos+2);if(end<0)return false;
 if(!silent){const token=parser.push('text','',0);token.content=parser.src.slice(parser.pos,end+2);}
 parser.pos=end+2;return true;
});
if(hljs.getLanguage('cpp'))hljs.registerAliases('cuda',{languageName:'cpp'});
const state = {conversation:null,job:null,task:null,view:'chat',projects:[],poll:null,webSources:[],submitting:false,networkPolicyTouched:false,inspector:{open:false,wide:false,tab:'details',source:null,sourceIndex:0,sourceSet:[],metadata:null,preview:null}};
const welcome = $('#messages').innerHTML;
const terminal = new Set(['complete','failed','cancelled','interrupted']);
function element(tag,text,cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=String(text); if(cls)e.className=cls; return e; }
function button(text,action,cls) {const b=element('button',text,cls);b.type='button';b.onclick=()=>Promise.resolve().then(action).catch(notice);return b;}
function notice(error) {$('#notice').textContent=error.message||String(error);$('#notice').hidden=false;setTimeout(()=>$('#notice').hidden=true,7000);}
async function api(path,data) {
 let response;
 try{
  response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-Reverend-Token':token,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 }catch(_){
  throw Error('Reverend backend is unreachable. Restart Reverend, then refresh this page.');
 }
 let result;
 try{result=await response.json();}
 catch(_){throw Error('Reverend backend returned an invalid local response. Restart Reverend and retry.');}
 if(!response.ok)throw Error(result.error||'Local request failed');
 return result;
}
const sourceImageObjectUrls=new Map();
async function sourceImageObjectUrl(imageId){
 if(!/^[a-f0-9]{32}$/.test(String(imageId||'')))throw Error('Invalid local image identifier');
 if(sourceImageObjectUrls.has(imageId))return sourceImageObjectUrls.get(imageId);
 const response=await fetch('/api/research/images/'+encodeURIComponent(imageId),{headers:{'X-Reverend-Token':token}});
 if(!response.ok)throw Error('Local source image unavailable');
 const blob=await response.blob();
 if(!['image/png','image/jpeg','image/webp'].includes(blob.type)||!blob.size||blob.size>2000000)throw Error('Invalid local source image');
 const url=URL.createObjectURL(blob);sourceImageObjectUrls.set(imageId,url);return url;
}
window.attachSourceImage=(container,source,cls='source-image')=>{
 if(!container||!source?.image_id)return;
 sourceImageObjectUrl(source.image_id).then(url=>{if(!container.isConnected)return;const img=element('img');img.className=cls;img.alt=sourceTitle(source);img.loading='lazy';img.decoding='async';img.src=url;container.append(img);}).catch(()=>{});
};
window.addEventListener('beforeunload',()=>{for(const url of sourceImageObjectUrls.values())URL.revokeObjectURL(url);sourceImageObjectUrls.clear();});
function normalizeMarkdown(text) {
  const source=String(text||'');
  const lines=source.split(/\r?\n/);
  let first=0,last=lines.length-1;
  while(first<=last && lines[first].trim()==='')first++;
  while(last>=first && lines[last].trim()==='')last--;
  if(first>=last)return source;
  const opening=lines[first];
  const closing=lines[last];
  if(!opening.startsWith('```'))return source;
  const label=opening.slice(3).trimEnd().toLowerCase();
  if(label!=='markdown' && label!=='md')return source;
  if(!closing.startsWith('```') || closing.slice(3).trim()!=='')return source;
  return lines.slice(first+1,last).join('\n');
}
function markdown(target,text) {
  target.innerHTML=DOMPurify.sanitize(md.render(normalizeMarkdown(text)));
  target.querySelectorAll('a').forEach(a=>{a.target='_blank';a.rel='noopener noreferrer';if(!/^https?:/i.test(a.href))a.removeAttribute('href');});
  target.querySelectorAll('pre code').forEach(code=>{const language=(code.className.match(/language-([\w+-]+)/)||[])[1]||'code';const kind=language.toLowerCase();const source=code.textContent;const pre=code.parentElement;if(['mermaid','diagram'].includes(kind)){try{const shell=element('div',undefined,'diagram-block');const top=element('div',undefined,'diagram-toolbar');top.append(element('span','Flowchart'),button('Source',()=>openArtifactPreview('mermaid',source),'preview-code'),button('Copy',async()=>navigator.clipboard.writeText(source),'copy-code'));shell.append(top,window.renderReverendDiagram(source));pre.replaceWith(shell);return;}catch(error){const warning=element('div','Diagram could not be rendered safely: '+error.message,'diagram-error');pre.after(warning);}}try{hljs.highlightElement(code);}catch(_){}const bar=element('div',undefined,'code-toolbar');bar.append(element('span',language));const actions=element('span',undefined,'code-actions');if(['html','html-preview','artifact-html','preview-html','svg'].includes(kind)){const previewKind=kind==='svg'?'svg':'html';actions.append(button('Preview',()=>openArtifactPreview(previewKind,source),'preview-code'));}actions.append(button('Copy',async()=>{await navigator.clipboard.writeText(source);},'copy-code'));bar.append(actions);pre.prepend(bar);});
  renderMathInElement(target,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},{left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false}],throwOnError:false,trust:false,strict:'warn'});
}
function badge(text) {return element('span',text,'badge '+String(text).replace(/[^a-z]/g,''));}
function card(title) {const e=element('article',undefined,'card');e.append(element('h3',title));return e;}
function details(title,data) {const d=element('details');d.append(element('summary',title));const p=element('pre',typeof data==='string'?data:JSON.stringify(data,null,2));d.append(p);return d;}
function detailValue(value){if(Array.isArray(value))return value.join(', ');if(value&&typeof value==='object')return JSON.stringify(value);if(typeof value==='boolean')return value?'Yes':'No';return String(value);}
function inspectorPlaceholder(title='Nothing selected',text='Open a citation, response details, or a previewable code block.'){const empty=element('div',undefined,'inspector-empty');empty.append(element('strong',title),element('p',text));return empty;}
function inspectorDetailGrid(metadata={}){const normalized=metadata.response_details||{};const grid=element('div',undefined,'inspector-detail-grid');const labels={model:'Model & runtime',completion:'Completion',context:'Context',task:'Authoritative task',verification:'Verification',continuation:'Continuation',evidence:'Evidence',performance:'Performance',error:'Error'};for(const [sectionName,values] of Object.entries(normalized)){if(!values||typeof values!=='object'||!Object.keys(values).length)continue;const section=element('section',undefined,'inspector-detail-section');section.append(element('h4',labels[sectionName]||sectionName.replaceAll('_',' ')));const dl=element('dl');for(const [key,value] of Object.entries(values)){const item=element('div',undefined,'inspector-detail-row');item.append(element('dt',key.replaceAll('_',' ')),element('dd',detailValue(value)));dl.append(item);}section.append(dl);grid.append(section);}if(!grid.childElementCount)grid.append(inspectorPlaceholder('No structured details','This response has no structured runtime metadata.'));return grid;}
function setInspectorOpen(value){state.inspector.open=Boolean(value);document.body.classList.toggle('inspector-open',state.inspector.open);$('#inspector').setAttribute('aria-hidden',String(!state.inspector.open));$('#inspector-toggle').setAttribute('aria-expanded',String(state.inspector.open));}
function setInspectorWide(value){state.inspector.wide=Boolean(value);document.body.classList.toggle('inspector-wide',state.inspector.wide);}
function renderInspector(){
 const tab=state.inspector.tab;const box=$('#inspector-content');box.replaceChildren();document.querySelectorAll('[data-inspector-tab]').forEach(button=>{const selected=button.dataset.inspectorTab===tab;button.classList.toggle('active',selected);button.setAttribute('aria-selected',String(selected));});
 if(tab==='sources'){
  const source=state.inspector.source;if(!source){box.append(inspectorPlaceholder('No source selected','Open a source card or citation from an answer.'));return;}
  $('#inspector-title').textContent=sourceTitle(source);$('#inspector-subtitle').textContent=sourceDescription(source);
  box.append(element('div',`SOURCE ${state.inspector.sourceIndex+1}`,'eyebrow'));
  const sourceSet=state.inspector.sourceSet||[];
  if(sourceSet.length>1){const nav=element('div',undefined,'source-nav');const previous=button('← Previous',()=>selectInspectorSource(state.inspector.sourceIndex-1),'source-nav-button');const next=button('Next →',()=>selectInspectorSource(state.inspector.sourceIndex+1),'source-nav-button');previous.disabled=state.inspector.sourceIndex<=0;next.disabled=state.inspector.sourceIndex>=sourceSet.length-1;nav.append(previous,element('span',`${state.inspector.sourceIndex+1} of ${sourceSet.length}`),next);box.append(nav);}
  if(source.image_id){const imageHost=element('div',undefined,'source-inspector-image-host');box.append(imageHost);window.attachSourceImage(imageHost,source,'source-inspector-image');}
  box.append(element('blockquote',source.excerpt||source.content||'No stored excerpt.','source-excerpt'));
  const provenance=element('div',undefined,'source-provenance');
  for(const [label,value] of [['Trust',source.trust_class||source.source_trust||source.trust],['Freshness',source.search_freshness],['Provider',source.search_provider],['Published',source.published_at],['Recorded',source.synced_at||source.indexed_at||source.created_at]])if(value)provenance.append(element('span',`${label}: ${String(value).replaceAll('_',' ')}`));
  if(provenance.childElementCount)box.append(provenance);
  const original=source.source||source.url;if(original){let url;try{url=new URL(original);}catch(_){}if(url&&['https:','http:'].includes(url.protocol)&&!url.username&&!url.password){const link=element('a','Open original ↗','source-open');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';box.append(link);}else box.append(button('Copy original path',()=>navigator.clipboard.writeText(original),'source-open'));}
  box.append(details('Advanced provenance',Object.fromEntries(Object.entries(source).filter(([key])=>!['content','excerpt'].includes(key)))));
  return;
 }
 if(tab==='details'){
  $('#inspector-title').textContent='Response details';$('#inspector-subtitle').textContent='Model, context, verification, evidence, and timing';
  if(!state.inspector.metadata){box.append(inspectorPlaceholder('No response selected','Choose Details beneath an assistant response.'));return;}
  box.append(inspectorDetailGrid(state.inspector.metadata));
  box.append(details('Advanced metadata',Object.fromEntries(Object.entries(state.inspector.metadata).filter(([key])=>!['sources','response_details'].includes(key)))));
  return;
 }
 $('#inspector-title').textContent='Artifact preview';$('#inspector-subtitle').textContent='Local sandboxed rendering';
 const preview=state.inspector.preview;if(!preview){box.append(inspectorPlaceholder('No preview selected','Preview an HTML or SVG code block from a response.'));return;}
 const head=element('div',undefined,'preview-heading');const actions=element('div',undefined,'preview-actions');actions.append(button(state.inspector.wide?'Collapse':'Expand',()=>{setInspectorWide(!state.inspector.wide);renderInspector();},'preview-copy'),button('Copy source',()=>navigator.clipboard.writeText(preview.source),'preview-copy'));head.append(badge(preview.kind.toUpperCase()),actions);box.append(head);
 if(preview.kind==='mermaid'){
  try{box.append(window.renderReverendDiagram(preview.source));}catch(error){box.append(inspectorPlaceholder('Diagram could not render safely',error.message));}
 }else if(preview.kind==='html'){
  const frame=element('iframe',undefined,'artifact-frame');frame.setAttribute('sandbox','');frame.setAttribute('title','Sandboxed HTML preview');
  const clean=DOMPurify.sanitize(preview.source,{FORBID_TAGS:['script','iframe','object','embed','link','meta','base','form'],FORBID_ATTR:['srcdoc']});
  frame.srcdoc=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"><style>html{color-scheme:dark}body{margin:0;padding:20px;background:#0b1020;color:#e4eaf5;font:14px/1.55 system-ui,sans-serif}*{box-sizing:border-box}</style></head><body>${clean}</body></html>`;box.append(frame);
 }else{
  const previewBox=element('div',undefined,'svg-preview');previewBox.innerHTML=DOMPurify.sanitize(preview.source,{USE_PROFILES:{svg:true,svgFilters:true},FORBID_TAGS:['script','foreignObject','image','a']});box.append(previewBox);
 }
}
function openInspector(tab){if(tab!=='preview')setInspectorWide(false);state.inspector.tab=tab;setInspectorOpen(true);renderInspector();}
function selectInspectorSource(index){const sources=state.inspector.sourceSet||[];if(index<0||index>=sources.length)return;state.inspector.source=sources[index];state.inspector.sourceIndex=index;renderInspector();}
window.openInspectorSource=(source,index,sourceSet=[])=>{state.inspector.source=source;state.inspector.sourceIndex=index;state.inspector.sourceSet=Array.isArray(sourceSet)&&sourceSet.length?sourceSet:[source];openInspector('sources');};
function openInspectorDetails(metadata){state.inspector.metadata=metadata;openInspector('details');}
function openArtifactPreview(kind,source){state.inspector.preview={kind,source};openInspector('preview');}
function responseDetails(metadata={}) {
 const wrapper=element('details',undefined,'response-details');
 wrapper.append(element('summary','Response details'));
 const normalized=metadata.response_details||{};
 const labels={model:'Model & runtime',completion:'Completion',context:'Context',task:'Authoritative task',verification:'Verification',continuation:'Continuation',evidence:'Evidence',performance:'Performance',error:'Error'};
 if(Object.keys(normalized).length){
  const grid=element('div',undefined,'response-details-grid');
  for(const [sectionName,values] of Object.entries(normalized)){
   if(!values||typeof values!=='object')continue;
   const section=element('section',undefined,'response-detail-section');
   section.append(element('h4',labels[sectionName]||sectionName.replaceAll('_',' ')));
   const dl=element('dl');
   for(const [key,value] of Object.entries(values)){
    const item=element('div',undefined,'response-detail-row');
    item.append(element('dt',key.replaceAll('_',' ')),element('dd',detailValue(value)));
    dl.append(item);
   }
   section.append(dl);grid.append(section);
  }
  wrapper.append(grid);
 }
 const raw=Object.fromEntries(Object.entries(metadata).filter(([key])=>!['sources','response_details'].includes(key)));
 wrapper.append(details('Advanced metadata',raw));
 return wrapper;
}
function modelFromMetadata(metadata={}) {
 const runs=metadata.model_runs||metadata.response_details?.model?.runs||[];
 const last=Array.isArray(runs)?runs.filter(run=>run&&run.model).at(-1):null;
 return last?.model||metadata.model||metadata.answer_model||metadata.response_details?.model?.model||metadata.routing?.model_role||'Local models';
}
function firstFiniteNumber(...values) {
 for(const value of values){
  if(value===undefined||value===null||value==='')continue;
  const number=Number(value);if(Number.isFinite(number))return number;
 }
 return null;
}
function contextUsageFromMetadata(metadata={}) {
 const context=metadata.response_details?.context||{};
 const canonicalPercent=firstFiniteNumber(metadata.context_utilization_percent,context.context_utilization_percent);
 const inputBudget=firstFiniteNumber(metadata.input_budget_tokens,context.input_budget_tokens,metadata.prompt_token_budget,context.prompt_token_budget);
 const actualProvider=firstFiniteNumber(metadata.actual_provider_prompt_tokens,context.actual_provider_prompt_tokens);
 const estimated=firstFiniteNumber(metadata.estimated_prompt_tokens,context.estimated_prompt_tokens);
 const physicalPercent=firstFiniteNumber(metadata.physical_context_utilization_percent,context.physical_context_utilization_percent);
 if(canonicalPercent!==null)return {percent:Math.max(0,canonicalPercent),inputBudget,actualProvider,estimated,physicalPercent};
 const used=actualProvider??estimated;
 if(inputBudget===null||inputBudget<=0||used===null)return null;
 return {percent:Math.max(0,used/inputBudget*100),inputBudget,actualProvider,estimated,physicalPercent};
}
function updateTopbarMetadata(metadata={}) {
 const model=modelFromMetadata(metadata);
 const chip=$('#active-model');if(chip){chip.textContent=String(model).replaceAll('_',' ');chip.hidden=!model||model==='Local models';}
 const usageChip=$('#context-usage');if(!usageChip)return;
 const usage=contextUsageFromMetadata(metadata);
 if(!usage){usageChip.hidden=true;usageChip.className='context-usage-chip';usageChip.removeAttribute('title');return;}
 const percent=Math.round(usage.percent);
 const detail=['Safe input '+usage.percent.toFixed(usage.percent<10?1:0)+'%'];
 if(usage.inputBudget!==null)detail.push('budget '+usage.inputBudget.toLocaleString()+' tokens');
 if(usage.actualProvider!==null)detail.push('actual provider '+usage.actualProvider.toLocaleString()+' tokens');
 if(usage.estimated!==null)detail.push('estimate '+usage.estimated.toLocaleString()+' tokens');
 if(usage.physicalPercent!==null)detail.push('physical window '+usage.physicalPercent.toFixed(usage.physicalPercent<10?1:0)+'%');
 usageChip.hidden=false;
 usageChip.textContent='Input '+percent+'%';
 usageChip.title=detail.join(' · ');
 usageChip.className='context-usage-chip'+(percent>=92?' critical':percent>=80?' warning':'');
}
function filterConversations() {
 const query=($('#conversation-search')?.value||'').trim().toLowerCase();
 document.querySelectorAll('#conversations .conversation-row').forEach(row=>{const title=row.querySelector('.conversation-open')?.textContent||'';row.hidden=Boolean(query)&&!title.toLowerCase().includes(query);});
}
function resizePrompt() {
 const prompt=$('#prompt');if(!prompt)return;
 prompt.style.height='auto';prompt.style.height=Math.min(Math.max(prompt.scrollHeight,52),220)+'px';
}
function defaultNetworkPolicy(mode) {return mode==='research'?'AUTO':mode==='develop'?'OFF':'ASK';}
function toggleSidebar() {
 const collapsed=document.body.classList.toggle('sidebar-collapsed');
 localStorage.setItem('reverend-sidebar-collapsed',collapsed?'1':'0');
 $('#sidebar-collapse')?.setAttribute('aria-pressed',String(collapsed));
}
async function approveWebRetry() {
 const messages=state.conversation?await api('messages?id='+encodeURIComponent(state.conversation)):[];
 const last=messages.filter(message=>message.role==='user').at(-1);if(!last)return;
 $('#network-policy').value='AUTO';syncNetworkPolicy(true);
 $('#prompt').value=last.content;resizePrompt();$('#composer').requestSubmit();
}
function message(role,content,metadata={}) {
  const row=element('article',undefined,'message '+role);row.append(element('div',role==='user'?'YOU':'REVEREND','message-label'));
  const body=element('div',undefined,'message-body markdown');markdown(body,content);row.append(body);
  if(role==='assistant') {const meta=element('div',undefined,'message-meta');const normalized=metadata.response_details||{};const completion=normalized.completion?.reason;const searched=metadata.evidence?.web_search?.attempted;meta.append(element('span',['Local',completion==='output_limit_reached'?'Partial':completion==='complete'?'Complete':metadata.cancelled?'Stopped':null,searched?'Web searched':null,metadata.sources?.length?`${metadata.sources.length} sources`:null].filter(Boolean).join(' · ')),button('Details',()=>openInspectorDetails(metadata),'message-action'),button('Copy',()=>navigator.clipboard.writeText(content),'message-action'),button('Retry',retry,'message-action'));if(metadata.issues?.some(issue=>issue.code==='network_approval_required'))meta.append(button('Approve web & retry',approveWebRetry,'message-action web-approve'));row.append(meta);if(metadata.sources?.length){linkCitations(body,metadata.sources);row.append(sourceList(metadata.sources));}}
  return row;
}
function showMessages(messages,job) {const latest=[...messages].reverse().find(message=>message.role==='assistant');if(job?.details)updateTopbarMetadata(job.details);else if(latest?.metadata)updateTopbarMetadata(latest.metadata);const box=$('#messages');const oldScroll=box.scrollTop;const nearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<160;box.replaceChildren();if(!messages.length&&!job){box.innerHTML=welcome;bindSuggestions();}else{messages.forEach(m=>box.append(message(m.role,m.content,m.metadata)));if(job&&!terminal.has(job.status)){const row=message('assistant',job.response||({queued:'Waiting for the local model…',stopping:'Stopping…'}[job.status]||'Working on your request…'),job.details);row.classList.add('streaming');const body=row.querySelector('.message-body');row.insertBefore(liveActivity(job),body);box.append(row);}}box.scrollTop=nearBottom?box.scrollHeight:oldScroll;}
async function renameConversation(conversation){
 const next=window.prompt('Rename conversation',conversation.title||'');
 if(next===null)return;
 const title=next.trim();if(!title){notice(Error('Conversation title cannot be empty.'));return;}
 const updated=await api('conversations/rename',{id:conversation.id,title});
 if(state.conversation===conversation.id)$('#view-title').textContent=updated.title;
 await conversations();
}
async function deleteConversation(conversation){
 if(!window.confirm('Delete "'+(conversation.title||'this conversation')+'"? This removes its local messages and task state.'))return;
 await api('conversations/delete',{id:conversation.id});
 if(state.conversation===conversation.id){state.conversation=null;state.job=null;await newChat();return;}
 await conversations();
}
async function conversations() {
 const items=await api('conversations');const box=$('#conversations');box.replaceChildren();
 for(const c of items){
  const row=element('div',undefined,'conversation-row'+(c.id===state.conversation?' selected':''));
  const open=button(c.title,()=>openConversation(c.id,c.privacy_mode||'normal',c.title),'conversation-open');open.title=c.title;
  const actions=element('span',undefined,'conversation-actions');
  const rename=button('✎',()=>renameConversation(c),'conversation-action');rename.title='Rename conversation';rename.setAttribute('aria-label','Rename '+c.title);
  const remove=button('×',()=>deleteConversation(c),'conversation-action danger-action');remove.title='Delete conversation';remove.setAttribute('aria-label','Delete '+c.title);
  actions.append(rename,remove);row.append(open,actions);box.append(row);
 }
 filterConversations();
}
async function openConversation(id,privacyMode='normal',title='') {state.conversation=id;state.job=null;$('#privacy-mode').value=privacyMode;$('#privacy-mode').disabled=true;syncPrivacy();await view('chat');const messages=await api('messages?id='+encodeURIComponent(id));showMessages(messages);const jobs=await api('jobs');const active=jobs.find(j=>j.conversation_id===id&&!terminal.has(j.status));if(active){state.job=active.id;watch(active.id);}busy(Boolean(active));await conversations();$('#view-title').textContent=title||messages[0]?.content.slice(0,60)||'New conversation';}
async function newChat() {state.conversation=null;state.job=null;state.networkPolicyTouched=false;$('#privacy-mode').value='normal';$('#privacy-mode').disabled=false;syncPrivacy();$('#network-policy').value=defaultNetworkPolicy($('#mode').value);syncNetworkPolicy(false);busy(false);await view('chat');showMessages([]);$('#view-title').textContent='New conversation';$('#prompt').focus();await conversations();}
function busy(value,develop=false) {$('#send').disabled=value;$('#stop').hidden=!value||develop;$('#stop').disabled=false;$('#prompt').disabled=value;$('#generation-state').textContent=value?(develop?'Developing…':'Working locally…'):'';$('#composer').setAttribute('aria-busy',String(value));}
function generationLabel(job){if(job.status==='stopping')return 'Stopping…';const web=job.details?.evidence?.web_search;if(!job.response&&web?.attempted)return web.fetched_count?'Reading web sources…':'Searching the web…';if(!job.response&&Number(job.details?.retrieval_rounds||0)>0)return 'Searching local knowledge…';return job.response?'Writing…':'Reasoning locally…';}
function activityStep(label,detail,status='pending'){
 const step=element('div',undefined,'activity-step '+status);
 step.append(element('span','', 'activity-dot'),element('strong',label),element('small',detail));
 return step;
}
function liveActivity(job){
 const details=job.details||{};const evidence=details.evidence||{};const web=evidence.web_search||{};
 const sources=Array.isArray(details.sources)?details.sources:[];
 const strip=element('section',undefined,'activity-ribbon');
 const head=element('div',undefined,'activity-ribbon-head');
 const provider=web.provider||web.status?.provider;
 const freshness=web.freshness&&web.freshness!=='stable'?web.freshness:null;
 const activityLabel=web.attempted?'Researching':Number(details.retrieval_rounds||0)>0?'Retrieving':'Working locally';
 head.append(element('strong',activityLabel),element('span',[provider,freshness].filter(Boolean).join(' · ')||'Local execution'));
 strip.append(head);
 const steps=element('div',undefined,'activity-steps');
 const routed=Boolean(details.routing||details.understanding);
 const retrieval=Number(details.retrieval_rounds||0);
 const searched=Boolean(web.attempted);
 const fetched=Number(web.fetched_count||0);
 const searchDetail=searched?(fetched?(String(fetched)+' web source'+(fetched===1?'':'s')+' fetched'):(web.search_result_count?(String(web.search_result_count)+' results found'):'Searching fresh sources')):(retrieval?(String(retrieval)+' local retrieval round'+(retrieval===1?'':'s')):'No retrieval needed');
 const readDetail=sources.length?(String(sources.length)+' source'+(sources.length===1?'':'s')+' accepted'):(searched?'Evaluating evidence':'Waiting for evidence');
 steps.append(
  activityStep('Route',routed?(details.routing?.model_role||details.role||'Workflow selected'):'Understanding request',routed?'complete':'active'),
  activityStep('Search',searchDetail,searched||retrieval?(fetched||sources.length?'complete':'active'):(job.response?'complete':'pending')),
  activityStep('Read',readDetail,sources.length?'complete':searched?'active':'pending'),
  activityStep('Answer',job.response?'Streaming response':job.status==='stopping'?'Stopping':'Preparing response',job.response?'active':'pending')
 );
 strip.append(steps);
 return strip;
}
async function retry() {const messages=state.conversation?await api('messages?id='+state.conversation):[];const last=messages.filter(m=>m.role==='user').at(-1);if(last){$('#prompt').value=last.content;$('#prompt').focus();}}
function bindSuggestions() {document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('#prompt').value=b.dataset.prompt;$('#prompt').focus();});document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view).catch(notice));}
async function view(name) {state.view=name;document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===name+'-view'));document.querySelectorAll('nav [data-view]').forEach(b=>{const active=b.dataset.view===name;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});document.body.classList.remove('menu-open');$('#inspector-toggle').hidden=name!=='chat';if(name!=='chat')setInspectorOpen(false);$('#view-title').textContent={chat:'Conversation',projects:'Projects',knowledge:'Knowledge',tasks:'Development tasks','control-plane':'Control plane',status:'System status'}[name];if(name==='projects')await projects();if(name==='tasks')await tasks();if(name==='control-plane')await controlPlane();if(name==='status')await status();}
async function projects() {state.projects=await api('projects');const select=$('#project-select');const selected=select.value;select.replaceChildren(new Option('No project context',''));const box=$('#projects');box.replaceChildren();for(const p of state.projects){select.add(new Option(p.name,p.id));const c=card(p.name);c.append(element('p',p.repo_real_path,'path'),badge(p.trust_mode),element('p',`${p.branch||'Unknown branch'} · ${p.dirty?'Uncommitted changes':'Clean checkout'}`),element('small',(p.head||'').slice(0,12)+' · '+Object.keys(p.languages||{}).join(', ')+' · '+(p.build_systems||[]).join(', ')+' · '+(p.tests||0)+' test files'),button('Use project',async()=>{select.value=p.id;contextChips();$('#mode').value='develop';modeChanged();await view('chat');$('#prompt').focus();}));c.append(button('Build semantic index',async()=>{const job=await api('code/index',{project_id:p.id});notice('Indexing local code. Progress is in System status.');state.job=job.job_id;watch(job.job_id);}));if(p.error)c.append(element('p',p.error));box.append(c);}if(!state.projects.length)box.append(element('p','Register a local Git repository to begin.','empty-state'));select.value=selected;}
function syncPrivacy(){
 const select=$('#privacy-mode');const pill=$('#privacy-pill');if(!select||!pill)return;
 const labels={normal:'Normal',private:'Private',ephemeral:'Ephemeral'};
 pill.textContent=labels[select.value]||'Normal';
 pill.className='privacy-pill '+select.value;
 pill.title={normal:'Persistent conversation',private:'Persistent without memory promotion',ephemeral:'Session-only conversation'}[select.value]||'Conversation privacy';
}
function syncNetworkPolicy(userInitiated=true){
 if(userInitiated)state.networkPolicyTouched=true;
 const select=$('#network-policy');const policy=select.value;
 const labels={ASK:'◎ Web ask',AUTO:'◎ Web auto',OFF:'◎ Web off'};
 const pill=$('#web-policy-pill');pill.textContent=labels[policy]||'◎ Web';pill.classList.toggle('active',policy==='AUTO');pill.classList.toggle('ask',policy==='ASK');pill.setAttribute('aria-pressed',String(policy==='AUTO'));
 const mode=$('#mode').value;const modeName=$('#mode').selectedOptions[0]?.textContent||'Auto';
 if($('#active-workflow'))$('#active-workflow').textContent=modeName+' · web '+policy.toLowerCase();
}
function modeChanged() {
 const mode=$('#mode').value;
 if(!state.networkPolicyTouched)$('#network-policy').value=defaultNetworkPolicy(mode);
 syncNetworkPolicy(false);
 $('#acceptance-row').hidden=mode!=='develop';
 $('#mode-summary').textContent=$('#mode').selectedOptions[0].textContent;
 const help={auto:'Automatic routing with approval before fresh network access.',ask:'Fast local answer; asks before required web access.',reason:'Deep local reasoning; asks before required web access.',research:'Evidence-first research with automatic fresh web search.',develop:'Plan → implement → verify in an isolated worktree.'}[mode];
 $('#model-label').textContent=help;const workflowHelp=$('#workflow-help');if(workflowHelp)workflowHelp.textContent=help;
}
$('#composer').onsubmit=async e=>{
 e.preventDefault();if(state.submitting||$('#send').disabled)return;
 const text=$('#prompt').value.trim();if(!text)return;
 const mode=$('#mode').value;const project_id=$('#project-select').value||null;
 if(mode==='develop'&&!project_id){notice('Select a registered project before developing');return;}
 state.submitting=true;busy(true,mode==='develop');$('#stop').hidden=true;$('#composer-options').open=false;
 try{
  const result=mode==='develop'?await api('develop',{project_id,request:text,acceptance:$('#acceptance').value}):await api('chat',{text,mode,project_id,conversation_id:state.conversation,knowledge:$('#use-knowledge').checked,web_source_ids:state.webSources,network_policy:$('#network-policy').value,...(state.conversation?{}:{privacy_mode:$('#privacy-mode').value})});
  state.job=result.job_id;
  if(mode==='develop'||result.kind==='develop'){state.devRequest=text;await view('chat');showDevelopment({status:'queued',details:{}});}
  else{state.conversation=result.conversation_id;$('#privacy-mode').disabled=true;showMessages(await api('messages?id='+state.conversation),{status:'queued',response:'',details:{}});await conversations();}
  $('#prompt').value='';resizePrompt();state.webSources=[];busy(true,mode==='develop'||result.kind==='develop');watch(result.job_id);
 }catch(error){busy(false);notice(error);}finally{state.submitting=false;}
};
async function watch(identity) {clearTimeout(state.poll);try{const job=await api('jobs/'+identity);if(state.job!==identity)return;updateTopbarMetadata(job.details||{});if(job.kind==='chat'&&state.view==='chat'&&state.conversation===job.conversation_id){const messages=await api('messages?id='+job.conversation_id);if(state.job!==identity||state.conversation!==job.conversation_id)return;showMessages(messages,job);$('#generation-state').textContent=generationLabel(job);}if(job.kind==='develop'&&state.view==='chat')showDevelopment(job);if(job.kind==='develop'&&job.task_id){state.task=job.task_id;if(state.view==='tasks'){await tasks();await task(job.task_id,job);}}if(terminal.has(job.status)){busy(false);state.job=null;if(job.status==='failed'||job.status==='interrupted')notice(job.details.error||'Job interrupted; retry when the runtime is ready');await conversations();return;}state.poll=setTimeout(()=>watch(identity),500);}catch(error){notice(error);state.poll=setTimeout(()=>watch(identity),2000);}}
$('#stop').onclick=async()=>{try{if(state.job){$('#stop').disabled=true;$('#generation-state').textContent='Stopping…';await api('cancel/'+state.job,{});}}catch(e){notice(e);}};
$('#new-chat').onclick=()=>newChat().catch(notice);$('.brand').onclick=e=>{e.preventDefault();newChat().catch(notice);};$('#mode').onchange=modeChanged;$('#privacy-mode').onchange=syncPrivacy;$('#network-policy').onchange=()=>syncNetworkPolicy(true);$('#web-policy-pill').onclick=()=>{const order=['ASK','AUTO','OFF'];const current=$('#network-policy').value;$('#network-policy').value=order[(order.indexOf(current)+1)%order.length];syncNetworkPolicy(true);};$('#menu-toggle').onclick=()=>document.body.classList.toggle('menu-open');$('#sidebar-collapse').onclick=toggleSidebar;$('#conversation-search').oninput=filterConversations;
$('#prompt').oninput=resizePrompt;$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#composer').requestSubmit();}};
document.onkeydown=e=>{if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();newChat().catch(notice);}else if(e.key==='Escape'&&state.inspector.open){setInspectorWide(false);setInspectorOpen(false);}};
$('#register-project').onsubmit=async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(e.target));await api('projects',data);e.target.reset();await projects();}catch(error){notice(error);}};
$('#knowledge-search').onsubmit=async e=>{e.preventDefault();const box=$('#knowledge-results');box.replaceChildren(element('p','Searching local sources…'));try{const results=await api('knowledge',Object.fromEntries(new FormData(e.target)));box.replaceChildren();results.forEach((r,i)=>{const c=sourceList([r]);c.append(element('p',(r.content||'').slice(0,500),'source-search-excerpt'));box.append(c);});if(!results.length)box.append(element('p','No matching sources.','empty-state'));}catch(error){box.replaceChildren();notice(error);}};
function developmentStageKey(phase){
 if(['preparing','plan'].includes(phase))return 'plan';
 if(['implementation','edits'].includes(phase))return 'implement';
 if(['verification','fresh_verifier','semantic_repair','workers'].includes(phase))return 'verify';
 return 'plan';
}
function developmentStageState(taskData={},job={}){
 const details=job?.details||{};const changed=taskData.changed_paths||details.edits?.changed_paths||[];
 const outcome=details.result||null;const phase=details.phase||'preparing';
 const statuses={plan:'pending',implement:'pending',verify:'pending'};
 const stage=developmentStageKey(phase);
 const setPriorComplete=target=>{
  if(target==='implement'||target==='verify')statuses.plan='complete';
  if(target==='verify')statuses.implement='complete';
 };
 if(stage==='plan'){
  statuses.plan=(details.plan?.stage_status==='complete'||details.plan?.summary)?'complete':'active';
 }else if(stage==='implement'){
  statuses.plan='complete';
  statuses.implement=(details.edits?.stage_status==='complete'||changed.length)?'complete':'active';
 }else{
  statuses.plan='complete';statuses.implement='complete';
  const verifyStage=details.fresh_verifier?.stage_status||details.verification?.stage_status||details.phase_status;
  statuses.verify=verifyStage==='complete'?'complete':verifyStage==='failed'?'failed':verifyStage==='blocked'?'blocked':'active';
 }
 if(outcome?.status==='pass'){
  statuses.plan='complete';statuses.implement='complete';statuses.verify='complete';
 }else if(outcome?.status==='fail'||outcome?.status==='failed'){
  statuses.plan='complete';statuses.implement='complete';statuses.verify='failed';
 }else if(outcome?.status==='unverified'){
  statuses.plan='complete';statuses.implement='complete';statuses.verify='blocked';
 }else if(outcome?.status==='blocked'){
  const blockedStage=developmentStageKey(phase);setPriorComplete(blockedStage);statuses[blockedStage]='blocked';
 }
 if(job?.status==='failed'||job?.status==='interrupted'){
  const failedStage=developmentStageKey(details.failed_phase||phase||'preparing');
  statuses.plan='pending';statuses.implement='pending';statuses.verify='pending';
  setPriorComplete(failedStage);statuses[failedStage]='failed';
 }
 return {phase,stage,statuses,changed,outcome};
}
window.developmentStageState=developmentStageState;
function phaseNode(label,description,status){
 const node=element('div',undefined,'phase-node '+status);
 const icon=status==='complete'?'✓':['failed','blocked'].includes(status)?'!':'';
 node.append(element('span',icon,'phase-icon'),element('strong',label),element('small',description));
 return node;
}
function developmentPipeline(taskData={},job={}){
 const details=job?.details||{};const verifications=taskData.verifications||[];
 const stageState=developmentStageState(taskData,job);const changed=stageState.changed;const outcome=stageState.outcome;
 const rail=element('section',undefined,'phase-rail');
 rail.append(
  phaseNode('Plan',details.plan?.summary||'Translate the request into bounded implementation work.',stageState.statuses.plan),
  phaseNode('Implement',changed.length?(String(changed.length)+' changed file'+(changed.length===1?'':'s')):'Apply isolated repository edits.',stageState.statuses.implement),
  phaseNode('Verify',outcome?.message||(verifications.length?(String(verifications.length)+' recorded check'+(verifications.length===1?'':'s')):'Run checks, repairs, and fresh review.'),stageState.statuses.verify)
 );
 return rail;
}
async function tasks() {const list=await api('tasks');const box=$('#tasks');box.replaceChildren();for(const t of list){const b=button('',()=>task(t.id),'task-item');b.append(element('strong',t.request||t.title||t.id),badge(t.state||t.status),element('small',t.created_at));box.append(b);}if(!list.length)box.append(element('p','Development tasks and their evidence will appear here.','empty-state'));}
async function task(id,job) {state.task=id;const t=await api('tasks/'+id);const box=$('#task-detail');box.replaceChildren();const heading=card(t.request||t.title||'Development task');heading.append(badge(t.state),element('p','Acceptance: '+(t.acceptance_criteria||'See task request')),element('p','Isolated worktree: '+(t.worktree_path||'Preparing'),'path'),element('p','Branch: '+(t.branch_name||t.worktree_branch||'Preparing')));box.append(heading);
  if(!job){const jobs=await api('jobs');const entry=jobs.find(j=>j.task_id===id);if(entry)job=await api('jobs/'+entry.id);}
  box.append(developmentPipeline(t,job||{}));
  if(job?.details.plan){const plan=card('Plan');const p=job.details.plan;for(const [key,value]of Object.entries(p))plan.append(details(key.replaceAll('_',' '),value));box.append(plan);}
  const changes=card('Changes');for(const path of t.changed_paths)changes.append(button(path,async()=>{const data=await api('diff',{identity:id,path});const pre=element('pre',undefined,'diff');for(const line of data.diff.split('\n'))pre.append(element('div',line,line.startsWith('+')?'added':line.startsWith('-')?'removed':''));const dialog=$('#artifact-dialog');$('#artifact-output').replaceChildren(pre);dialog.showModal();}));if(!t.changed_paths.length)changes.append(element('p','No changed files yet.'));box.append(changes);
  const checks=card('Verification & repair evidence');for(const v of t.verifications){const row=element('div',undefined,'verification');row.append(badge(v.status),element('strong',v.name||v.kind||'Check'));let evidence;try{evidence=JSON.parse(v.details_json||v.metadata_json||'{}');}catch(_){evidence={};}row.append(element('p',v.summary||''),details('Evidence',evidence));checks.append(row);}if(!t.verifications.length)checks.append(element('p','Waiting for verification.'));box.append(checks);
  if(job?.details.fresh_verifier)box.append(details('Fresh verifier result',job.details.fresh_verifier));if(job?.details.result)box.append(details('Outcome',job.details.result));
  const artifacts=card('Recorded output');for(const a of t.artifacts)artifacts.append(button(a.kind+' · '+a.path.split('/').at(-1),async()=>{const data=await api('artifacts/'+a.id);$('#artifact-output').textContent=data.content+(data.clipped?'\n[Output clipped]':'');$('#artifact-dialog').showModal();}));box.append(artifacts,details('Model runs',t.model_runs));
}
$('#close-dialog').onclick=()=>$('#artifact-dialog').close();
async function controlPlane(){
 const box=$('#control-plane');box.replaceChildren(element('p','Reading authoritative runtime state…'));
 const s=await api('control-plane');box.replaceChildren();
 const summary=card('Wave runtime');
 summary.append(badge(s.read_only?'Read only':'Mutable'),element('p',`${s.counts.workflows} workflows · ${s.counts.tasks} tasks · ${s.counts.jobs} jobs`),element('small',`${s.counts.specialists} specialists · ${s.counts.models} model roles · ${s.counts.artifacts} artifacts`));
 box.append(summary);
 const workflows=card('Workflows & tasks');
 for(const w of s.workflows.slice(0,12))workflows.append(element('p',`${w.status} · ${w.objective}`),element('small',w.id));
 if(!s.workflows.length)workflows.append(element('p','No vNext workflows recorded yet.','empty-state'));
 workflows.append(details('Recent tasks',s.tasks.slice(0,30)),details('Job attempts',s.jobs.slice(0,30)));box.append(workflows);
 const specialists=card('Specialists');
 for(const sp of s.specialists)specialists.append(element('p',`${sp.name} · ${sp.model_role} · ${sp.authority_profile}`),element('small',sp.methodology));
 box.append(specialists);
 const resources=card('Models & resources');
 resources.append(element('p','Loaded: '+((s.loaded_models||[]).map(m=>m.name||m.model||m).join(', ')||'None')),details('Model profiles',s.models),details('Resource events',s.resources?.events||[]));box.append(resources);
 const artifacts=card('Artifacts');
 for(const a of s.artifacts.slice(0,20))artifacts.append(element('p',`${a.artifact_type} · ${a.validation_state} · ${a.promotion_state}`),element('small',a.id));
 if(!s.artifacts.length)artifacts.append(element('p','No vNext artifacts recorded yet.','empty-state'));
 box.append(artifacts);
 const verification=card('Verification');
 verification.append(details('Recent verification events',s.verification?.events||[]));box.append(verification);
}
async function status() {const box=$('#status');box.replaceChildren(element('p','Checking local runtime…'));const s=await api('status');box.replaceChildren();const health=card('Runtime');health.append(badge('Local only'),element('p','Reverend '+s.version),details('Ollama',s.ollama),details('Knowledge health',s.knowledge));box.append(health);const search=card('Web research');const searchState=s.web_search||{configured:false};search.append(badge(searchState.configured?'Configured':'Disabled'),element('p',searchState.configured?`${searchState.provider} · ${searchState.endpoint_host||'configured endpoint'}`:'No automatic web-search provider configured.'),element('small','Network policy still controls every chat request. Search content remains untrusted until gated.'));if(searchState.error)search.append(element('p',searchState.error,'muted'));box.append(search);const models=card('Models');models.append(element('p','Loaded: '+(s.loaded_models.join(', ')||'None')));for(const r of s.roles)models.append(element('p',`${r.role} · ${r.model} · ${r.context.toLocaleString()} context`));box.append(models);const jobs=card('Recent activity');for(const j of s.jobs.slice(0,12))jobs.append(element('p',j.kind+' · '+j.status+' · '+j.created_at));box.append(jobs);}
bindSuggestions();Promise.all([conversations(),projects()]).catch(notice);

async function memories(query='') {const project_id=$('#project-select').value;if(!project_id)throw Error('Select a project in Conversations first');const rows=await api('memory/search',{project_id,query});const box=$('#memory-results');box.replaceChildren();for(const r of rows){const c=card(r.kind);c.append(element('p',r.content),element('small',r.source+' · '+r.created_at),details('Provenance',r),button('Archive',async()=>{await api('memory/archive',{identity:r.id});await memories(query);}));box.append(c);}if(!rows.length)box.append(element('p','No active matching records.'));}
$('#memory-search').onsubmit=e=>{e.preventDefault();memories(new FormData(e.target).get('query')).catch(notice);};
$('#memory-add').onsubmit=async e=>{e.preventDefault();try{const project_id=$('#project-select').value;if(!project_id)throw Error('Select a project first');await api('memory/add',{...Object.fromEntries(new FormData(e.target)),project_id});e.target.reset();await memories();}catch(error){notice(error);}};

$('#public-fetch').onsubmit=async e=>{e.preventDefault();try{const values=new FormData(e.target);const result=await api('research/fetch',{url:values.get('url'),allow_network:values.get('allow_network')==='on'});const box=$('#public-source');box.replaceChildren(element('p','Fetching in the restricted worker…'));const poll=async()=>{try{const job=await api('jobs/'+result.job_id);if(!terminal.has(job.status)){setTimeout(poll,500);return;}if(job.status!=='complete')throw Error(job.details.error||'Research failed');const r=job.details;const c=card('UNTRUSTED_EXTERNAL');c.append(element('p',r.url),element('p',r.content.slice(0,2000)),button('Use in next chat',()=>{state.webSources=[r.id];notice('Public source selected for your next message.');}),details('Provenance',{id:r.id,hash:r.content_hash,created_at:r.created_at}));box.replaceChildren(c);}catch(error){box.replaceChildren();notice(error);}};poll();}catch(error){notice(error);}};

function contextChips(){const box=$('#context-chips');box.replaceChildren();const select=$('#project-select');if(select.value)box.append(button(select.selectedOptions[0].textContent+' ×',()=>{select.value='';contextChips();},'context-chip'));}
$('#project-select').addEventListener('change',contextChips);
$('#add-context').onclick=()=>{$('#composer-options').open=!$('#composer-options').open;$('#project-select').focus();};
$('#close-source').onclick=()=>$('#source-dialog').close();
$('#inspector-toggle').onclick=()=>{if(state.inspector.open)setInspectorOpen(false);else openInspector(state.inspector.tab||'details');};
$('#inspector-close').onclick=()=>{setInspectorWide(false);setInspectorOpen(false);};$('#inspector-expand').onclick=()=>{setInspectorWide(!state.inspector.wide);renderInspector();};
document.querySelectorAll('[data-inspector-tab]').forEach(button=>button.onclick=()=>openInspector(button.dataset.inspectorTab));
if(localStorage.getItem('reverend-sidebar-collapsed')==='1'){document.body.classList.add('sidebar-collapsed');$('#sidebar-collapse')?.setAttribute('aria-pressed','true');}
resizePrompt();syncPrivacy();modeChanged();

function showDevelopment(job){
 const box=$('#messages');box.replaceChildren(message('user',state.devRequest||'Development request'));
 const c=card('Development task');c.classList.add('development-activity');
 const details=job.details||{};const outcome=details.result;const stageState=developmentStageState({changed_paths:details.edits?.changed_paths||[]},job);
 const phases={preparing:'Preparing an isolated worktree…',plan:'Planning the change',implementation:'Generating the implementation',edits:'Applying structured edits',verification:'Running checks and bounded repairs',fresh_verifier:'Reviewing the result independently',semantic_repair:'Repairing after independent review'};
 const failedStage=developmentStageKey(details.failed_phase||details.phase||'preparing');
 const failedLabels={plan:'planning',implement:'implementation',verify:'verification'};
 let statusText=outcome?.message||phases[details.phase]||'Preparing an isolated worktree…';
 if(job.status==='failed')statusText='Development failed during '+failedLabels[failedStage]+'.';
 else if(job.status==='interrupted')statusText='Development was interrupted during '+failedLabels[failedStage]+'.';
 c.append(element('p',statusText));
 if((job.status==='failed'||job.status==='interrupted')&&details.error)c.append(element('p',details.error,'development-error'));
 c.append(developmentPipeline({changed_paths:details.edits?.changed_paths||[]},job));
 if(details.plan?.summary)c.append(element('p',details.plan.summary));
 if(details.edits?.changed_paths)c.append(element('small',details.edits.changed_paths.length+' files changed'));
 if(job.task_id)c.append(button('Inspect changes and verification →',async()=>{await view('tasks');await task(job.task_id,job);}));
 if(outcome)c.append(badge(outcome.status==='pass'?'Verified':outcome.status));
 box.append(c);box.scrollTop=box.scrollHeight;
}
