'use strict';
function sourceEvidenceTags(source) {
  const tags=[];
  if(source.source_authority)tags.push(String(source.source_authority).replaceAll('_',' '));
  if(source.source_transport==='fetched_page')tags.push('Fetched page');
  else if(source.source_transport==='search_snippet')tags.push('Search snippet');
  if(source.fetch_status&&source.fetch_status!=='fetched'&&source.fetch_status!=='ok')tags.push(String(source.fetch_status).replaceAll('_',' '));
  return [...new Set(tags)].slice(0,3);
}
// Rendering only: relevance and corpus selection belong to the application service.
function sourceTitle(source) {
  if(source.source_title||source.title)return source.source_title||source.title;
  const path=source.source||source.url||'';
  if(/^https?:\/\//i.test(path)){try{const u=new URL(path);return decodeURIComponent(u.pathname.split('/').filter(Boolean).at(-1)||u.hostname);}catch(_){}}
  return path.split(/[\\/]/).at(-1)||'Source';
}
function sourceDescription(source) {
  const origin=source.search_provider?`Web · ${source.search_provider}`:(source.evidence_class||source.corpus);
  const freshness=source.search_freshness&&source.search_freshness!=='stable'?`Fresh · ${source.search_freshness}`:null;
  return [origin,freshness,source.section,source.page?`Page ${source.page}`:null].filter(Boolean).join(' · ')||'Local evidence';
}
function sourceDomain(source) {
  const raw=source.source||source.url||'';
  try{return new URL(raw).hostname.replace(/^www\./,'');}catch(_){return '';}
}
function sourceMeta(source) {
  const meta=element('span',undefined,'source-meta-row');
  const domain=sourceDomain(source);if(domain)meta.append(element('span',domain,'source-domain'));
  if(source.published_at)meta.append(element('span',String(source.published_at).slice(0,10),'source-date'));
  if(source.search_rank)meta.append(element('span','Result #'+String(source.search_rank),'source-rank'));
  if(source.search_freshness&&source.search_freshness!=='stable')meta.append(element('span',source.search_freshness,'source-freshness'));
  for(const tag of sourceEvidenceTags(source))meta.append(element('span',tag,'source-evidence-tag'));
  return meta;
}
function openSource(source,index,sourceSet=[source]) {
  if(typeof window.openInspectorSource==='function'){
    window.openInspectorSource(source,index,sourceSet);
    return;
  }
  const dialog=$('#source-dialog');const box=$('#source-detail');box.replaceChildren();
  box.append(element('div',`SOURCE ${index+1}`,'eyebrow'),element('h2',sourceTitle(source)),element('p',sourceDescription(source),'muted'));
  if(source.image_id&&typeof window.attachSourceImage==='function'){const imageHost=element('div',undefined,'source-inspector-image-host');box.append(imageHost);window.attachSourceImage(imageHost,source,'source-inspector-image');}
  box.append(element('blockquote',source.excerpt||source.content||'This older conversation has no stored excerpt.','source-excerpt'));
  const trust=source.trust_class||source.source_trust||source.trust;
  if(trust)box.append(element('p',String(trust).replaceAll('_',' '),'muted'));
  const synced=source.synced_at||source.indexed_at||source.created_at;
  if(synced)box.append(element('small','Recorded '+synced));
  const original=source.source||source.url;
  if(original){
    let url;try{url=new URL(original);}catch(_){}
    if(url&&['https:','http:'].includes(url.protocol)&&!url.username&&!url.password){const link=element('a','Open original ↗','source-open');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';box.append(link);}
    else box.append(button('Copy original path',()=>navigator.clipboard.writeText(original),'source-open'));
  }
  box.append(details('Advanced provenance',Object.fromEntries(Object.entries(source).filter(([key])=>!['content','excerpt'].includes(key)))));
  dialog.showModal();
}
function sourceList(sources) {
  const section=element('section',undefined,'sources');
  const heading=element('div',undefined,'sources-heading');
  heading.append(element('h3','Sources'),element('span',String(sources.length)+' accepted evidence item'+(sources.length===1?'':'s')));
  section.append(heading);
  const visuals=sources.map((source,index)=>({source,index})).filter(item=>item.source.image_id).slice(0,2);
  if(visuals.length&&typeof window.attachSourceImage==='function'){const gallery=element('div',undefined,'source-gallery');for(const item of visuals){const visual=button('',()=>openSource(item.source,item.index,sources),'source-gallery-item');const host=element('span',undefined,'source-gallery-image');visual.append(host,element('span',String(item.index+1)+' · '+sourceTitle(item.source),'source-gallery-caption'));window.attachSourceImage(host,item.source,'source-gallery-img');gallery.append(visual);}section.append(gallery);}
  const list=element('div',undefined,'source-card-list');
  sources.forEach((source,index)=>{const b=button('',()=>openSource(source,index,sources),'source-card');if(source.image_id&&typeof window.attachSourceImage==='function'){b.classList.add('has-image');const imageHost=element('span',undefined,'source-card-image');b.append(imageHost);window.attachSourceImage(imageHost,source,'source-thumbnail');}const number=element('span',String(index+1),'source-number');const content=element('span',undefined,'source-card-content');content.append(element('strong',sourceTitle(source)),element('small',sourceDescription(source)),sourceMeta(source));b.append(number,content);list.append(b);});
  section.append(list);return section;
}
function linkCitations(body,sources) {
  if(!sources.length)return;
  const labels=new Map();sources.forEach((s,i)=>{labels.set(String(i+1),i);labels.set(s.citation_label||'K'+(i+1),i);});
  const walker=document.createTreeWalker(body,NodeFilter.SHOW_TEXT);const nodes=[];
  while(walker.nextNode())if(!walker.currentNode.parentElement.closest('pre,code,a,button,.katex'))nodes.push(walker.currentNode);
  for(const node of nodes){const text=node.textContent;const matches=[...text.matchAll(/\[([A-Za-z0-9_-]+)\]/g)].filter(m=>labels.has(m[1]));if(!matches.length)continue;
    const fragment=document.createDocumentFragment();let end=0;
    for(const match of matches){fragment.append(document.createTextNode(text.slice(end,match.index)));const index=labels.get(match[1]);const b=button(String(index+1),()=>openSource(sources[index],index,sources),'citation');b.setAttribute('aria-label',`Open source ${index+1}: ${sourceTitle(sources[index])}`);fragment.append(b);end=match.index+match[0].length;}
    fragment.append(document.createTextNode(text.slice(end)));node.replaceWith(fragment);
  }
}
