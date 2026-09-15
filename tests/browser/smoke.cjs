const {chromium}=require('../../.browser-test/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const failures=[];page.on('pageerror',e=>failures.push(e.message));
 const external=[];page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8876/'))external.push(r.url());});
 await page.goto('http://127.0.0.1:8876/');

 // Canonical modern shell contract.
 assert.equal(await page.locator('#mode').inputValue(),'auto');
 assert.equal(await page.locator('#network-policy').inputValue(),'ASK');
 assert.equal((await page.locator('#web-policy-pill').innerText()).trim(),'◎ Web ask');
 assert.equal(await page.locator('#use-knowledge').isVisible(),false);
 assert.equal(await page.locator('#conversation-search').count(),1);
 assert.equal(await page.locator('#active-workflow').count(),1);
 assert.equal(await page.locator('#inspector').getAttribute('aria-hidden'),'true');
 assert.equal(await page.locator('#sidebar-collapse').count(),1);
 assert.equal((await page.locator('#privacy-pill').innerText()).trim(),'Normal');
 assert.equal(await page.locator('#context-usage').isHidden(),true);
 await page.evaluate(()=>{const select=document.querySelector('#privacy-mode');select.value='private';select.dispatchEvent(new Event('change',{bubbles:true}));});
 assert.equal((await page.locator('#privacy-pill').innerText()).trim(),'Private');
 await page.evaluate(()=>{const select=document.querySelector('#privacy-mode');select.value='normal';select.dispatchEvent(new Event('change',{bubbles:true}));});
 await page.evaluate(()=>updateTopbarMetadata({response_details:{model:{context_window:8192},context:{estimated_prompt_tokens:6144}}}));
 assert.equal(await page.locator('#context-usage').isHidden(),true);
 await page.evaluate(()=>updateTopbarMetadata({input_budget_tokens:6144,estimated_prompt_tokens:6144,actual_provider_prompt_tokens:6000,context_utilization_percent:100,physical_context_utilization_percent:75}));
 assert.equal((await page.locator('#context-usage').innerText()).trim(),'Input 100%');
 assert.match(await page.locator('#context-usage').getAttribute('title'),/actual provider 6,000 tokens/);
 assert.match(await page.locator('#context-usage').getAttribute('title'),/physical window 75%/);
 await page.evaluate(()=>updateTopbarMetadata({input_budget_tokens:6144,actual_provider_prompt_tokens:3072}));
 assert.equal((await page.locator('#context-usage').innerText()).trim(),'Input 50%');
 await page.evaluate(()=>updateTopbarMetadata({}));
 assert.equal(await page.locator('#context-usage').isHidden(),true);

 // Web policy cycles ASK -> AUTO -> OFF -> ASK without leaving the composer.
 await page.locator('#web-policy-pill').click();
 assert.equal(await page.locator('#network-policy').inputValue(),'AUTO');
 await page.locator('#web-policy-pill').click();
 assert.equal(await page.locator('#network-policy').inputValue(),'OFF');
 await page.locator('#web-policy-pill').click();
 assert.equal(await page.locator('#network-policy').inputValue(),'ASK');

 // Desktop navigation collapse is part of the canonical shell.
 await page.locator('#sidebar-collapse').click();
 assert.equal(await page.evaluate(()=>document.body.classList.contains('sidebar-collapsed')),true);
 await page.locator('#sidebar-collapse').click();
 assert.equal(await page.evaluate(()=>document.body.classList.contains('sidebar-collapsed')),false);

 await page.screenshot({path:'/tmp/reverend-home.png'});
 await page.locator('#prompt').fill('Explain a derivative and show code.');await page.locator('#send').click();
 await page.locator('.streaming').waitFor();
 await page.locator('.message.assistant:not(.streaming)').waitFor({timeout:10000});
 await page.locator('#send:enabled').waitFor({timeout:10000});
 assert.ok(await page.locator('.katex').count()>=2);
 assert.ok(await page.locator('.hljs-keyword').count()>0);
 assert.equal(await page.locator('.markdown table').count(),1);
 assert.equal(await page.evaluate(()=>window.injected),undefined);
 assert.ok(!(await page.locator('#messages').innerText()).includes('SECRET_REASONING'));
 await page.screenshot({path:'/tmp/reverend-chat.png'});
 await page.reload();await page.locator('#conversations .conversation-open').first().click();
 await page.locator('.katex').first().waitFor();
 await page.locator('#prompt').fill('A second response to cancel');await page.locator('#send').click();
 await page.locator('.streaming').waitFor();await page.locator('#stop').click();await page.locator('#send:enabled').waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.locator('#menu-toggle').click();await page.locator('nav [data-view="projects"]').click();
 assert.equal(await page.locator('#projects-view').isVisible(),true);
 assert.equal(await page.locator('nav [data-view="projects"]').getAttribute('aria-current'),'page');
 await page.locator('#menu-toggle').click();await page.locator('nav [data-view="chat"]').click();
 const fence=await page.evaluate(()=>{
  const host=document.createElement('div');
  markdown(host,'```markdown\n# Recovered heading\n\n```python\nprint("hello")\n```\n```');
  return {
    headings:host.querySelectorAll('h1').length,
    code:host.querySelector('pre code')?.textContent||'',
    language:host.querySelector('pre code')?.className||''
  };
 });
 assert.equal(fence.headings,1);
 assert.ok(fence.code.includes('print("hello")'));
 assert.ok(fence.language.includes('language-python'));

 const boundaries=await page.evaluate(()=>{
  const bt=String.fromCharCode(96).repeat(3);

  const whitespace=document.createElement('div');
  markdown(whitespace,'\n  \n'+bt+'markdown\n## Whitespace wrapper\n'+bt+'\n\n');

  const mdAlias=document.createElement('div');
  markdown(mdAlias,bt+'md\n### MD alias\n'+bt);

  const python=document.createElement('div');
  markdown(python,bt+'python\nprint("kept")\n'+bt);

  return {
    whitespaceHeadings:whitespace.querySelectorAll('h2').length,
    mdHeadings:mdAlias.querySelectorAll('h3').length,
    pythonCode:python.querySelector('pre code')?.textContent||'',
    pythonHeading:python.querySelectorAll('h1,h2,h3').length
  };
 });
 assert.equal(boundaries.whitespaceHeadings,1);
 assert.equal(boundaries.mdHeadings,1);
 assert.ok(boundaries.pythonCode.includes('print("kept")'));
 assert.equal(boundaries.pythonHeading,0);
 const mathAndLanguages=await page.evaluate(()=>{
  const host=document.createElement('div');markdown(host,String.raw`Inline \(a^2+b^2=c^2\) and display \[\sum_{i=1}^n i\]`);
  return {math:host.querySelectorAll('.katex').length,languages:['python','c','cpp','cuda','bash','json','yaml','javascript','typescript','rust'].filter(name=>!hljs.getLanguage(name))};
 });
 assert.equal(mathAndLanguages.math,2);assert.deepEqual(mathAndLanguages.languages,[]);

 // Citations now open the persistent Sources inspector, not the legacy modal.
 const sourceChecks=await page.evaluate(()=>{
  const source={source:'https://example.invalid/docs',source_title:'Safe source <img onerror=alert(1)>',corpus:'reference',section:'Derivatives',trust_class:'TRUSTED_REFERENCE',excerpt:'The derivative is 2x.',citation_label:'K1',source_authority:'primary',source_transport:'fetched_page'};
  const row=message('assistant','A supported statement [K1].',{sources:[source]});document.querySelector('#messages').append(row);
  return {cards:row.querySelectorAll('.source-card').length,citations:row.querySelectorAll('.citation').length,images:row.querySelectorAll('img').length};
 });
 assert.deepEqual(sourceChecks,{cards:1,citations:1,images:0});
 assert.equal(await page.locator('.source-card .source-evidence-tag').count(),2);
 await page.locator('.citation').last().click();
 assert.equal(await page.locator('#inspector').getAttribute('aria-hidden'),'false');
 assert.ok((await page.locator('#inspector-content .source-excerpt').innerText()).includes('2x'));
 assert.equal(await page.locator('#inspector-content details[open]').count(),0);
 assert.equal(await page.locator('#inspector-content .source-open').getAttribute('rel'),'noopener noreferrer');

 // Inspector expand/collapse is retained for sources and artifact previews.
 await page.locator('#inspector-expand').click();
 assert.equal(await page.evaluate(()=>document.body.classList.contains('inspector-wide')),true);
 await page.locator('#inspector-expand').click();
 assert.equal(await page.evaluate(()=>document.body.classList.contains('inspector-wide')),false);
 await page.locator('#inspector-close').click();
 assert.equal(await page.locator('#inspector').getAttribute('aria-hidden'),'true');

 // Canonical local diagram and sandboxed HTML artifact paths remain reachable.
 const artifactChecks=await page.evaluate(()=>{
  const bt=String.fromCharCode(96).repeat(3);
  const host=document.createElement('div');
  markdown(host,bt+'mermaid\nflowchart LR\nA[Start] --> B[Done]\n'+bt+'\n\n'+bt+'html\n<div><strong>Preview me</strong></div>\n'+bt);
  document.querySelector('#messages').append(host);
  return {diagrams:host.querySelectorAll('.diagram-block').length,previews:host.querySelectorAll('.preview-code').length};
 });
 assert.equal(artifactChecks.diagrams,1);
 assert.ok(artifactChecks.previews>=2);
 await page.locator('.preview-code').last().click();
 assert.equal(await page.locator('#inspector').getAttribute('aria-hidden'),'false');
 assert.equal(await page.locator('.artifact-frame').count(),1);
 assert.equal(await page.locator('.artifact-frame').getAttribute('sandbox'),'');
 await page.locator('#inspector-close').click();

 // Failed development jobs keep the failure on the stage that actually failed.
 const developmentFailure=await page.evaluate(()=>{
  state.devRequest='Implement the calculator';
  showDevelopment({
   status:'failed',
   details:{
    phase:'implementation',
    failed_phase:'implementation',
    phase_status:'failed',
    plan:{stage_status:'complete',summary:'Implement the calculator safely.'},
    error:'Coder failed before edits were applied'
   }
  });
  const nodes=[...document.querySelectorAll('.development-activity .phase-node')];
  return {
   classes:nodes.map(node=>node.className),
   heading:document.querySelector('.development-activity > p')?.textContent||'',
   error:document.querySelector('.development-error')?.textContent||''
  };
 });
 assert.ok(developmentFailure.classes[0].includes('complete'));
 assert.ok(developmentFailure.classes[1].includes('failed'));
 assert.ok(developmentFailure.classes[2].includes('pending'));
 assert.equal(developmentFailure.heading,'Development failed during implementation.');
 assert.equal(developmentFailure.error,'Coder failed before edits were applied');

 const blockedDevelopment=await page.evaluate(()=>window.developmentStageState({},{
  status:'complete',
  details:{
   phase:'plan',
   phase_status:'blocked',
   plan:{stage_status:'complete',summary:'Need more repository context.'},
   result:{status:'blocked',message:'Planning model requested additional context.'}
  }
 }));
 assert.equal(blockedDevelopment.statuses.plan,'blocked');
 assert.equal(blockedDevelopment.statuses.implement,'pending');
 assert.equal(blockedDevelopment.statuses.verify,'pending');

 await page.screenshot({path:'/tmp/reverend-mobile.png'});
 assert.deepEqual(failures,[]);assert.deepEqual(external,[]);
 console.log('GUI smoke passed: modern shell, web policy, inspector, artifacts, offline assets, streaming, Markdown, highlighting, math, XSS, persistence, stop, and mobile navigation.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
