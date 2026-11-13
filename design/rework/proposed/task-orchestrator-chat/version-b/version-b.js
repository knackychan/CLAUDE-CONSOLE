'use strict';
// Reuse Version A's fixtures, accounting, delivery gates and task-scoped drafts.
const baseB = {render,taskView,overview,stepView,composer,card,isAttention,setScenario,advance,routeName,activityText};
let bDock = $('window').clientWidth > 1050, bStepTab = 'chat';
const bScenarios = {
  planned:'52-B · Plan ready to start', 'plan-approval':'52-B · Confirm plan',
  'model-approval':'52-B · Scarce worker model hold', 'failed-twice':'52-B · Failed after repair',
  observed:'52-B · Observed session'
};
Object.assign(scenarioNames,bScenarios);
Object.assign(stateLabels,{planned:'Ready to start','plan-approval':'Plan to confirm','model-approval':'Worker model approval',failed:'Repair failed'});
isAttention = t => baseB.isAttention(t) || ['planned','plan-approval','model-approval','failed'].includes(t.status);
routeName = key => key ? baseB.routeName(key) : 'Not assigned';
activityText = t => t.status==='planned' ? 'No orchestrator assigned. Nothing has started.' : baseB.activityText(t);
const bIcons = {
  folder:'<path d="M2 5h5l2 2h13v13H2z"/><path d="M2 5V3h7l2 2"/>',
  terminal:'<rect x="2" y="3" width="20" height="18" rx="2"/><path d="m6 8 4 4-4 4m7 0h5"/>',
  handoff:'<path d="M14 3h7v7m0-7L10 14m8-1v7H3V5h7"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>'
};
const bIcon = name => '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+bIcons[name]+'</svg>';
const bButton = (label,action,primary=false) => `<button class="btn${primary?' primary':''}" data-b-action="${action}">${label}</button>`;
function bNavRow(t,pinned=false){
  const current=selected===t.id&&view==='task';
  return `<button class="b-nav-task ${isAttention(t)?'needs':''}" data-open="${esc(t.id)}" aria-current="${current}"><span class="b-nav-title">${esc(t.title)}</span><span class="b-nav-meta"><span class="b-source">run</span>${pinned?esc(t.project):esc(t.number)}<span>${esc(stateLabels[t.status])}</span></span></button>`;
}
function bProjectDock(){
  const needs=state.tasks.filter(isAttention),projects=[...new Set(state.tasks.map(t=>t.project)),'Paper Kite Docs'];
  return `<aside class="b-project-dock" aria-label="Project task navigator"><div class="b-dock-heading"><h2>Projects & tasks</h2><button class="btn" data-b-action="toggle-dock" aria-label="Close project navigator">Close</button></div><div class="b-needs" data-scroll="b-needs"><h3>Needs you · ${needs.length} · all projects</h3>${needs.map(t=>bNavRow(t,true)).join('')||'<p class="hint">No decisions waiting.</p>'}</div><div class="b-projects" data-scroll="b-projects">${projects.map(project=>{
    const tasks=state.tasks.filter(t=>t.project===project),modes=[...new Set(tasks.map(t=>t.mode))];
    return `<section class="b-project-group"><div class="b-project-label"><span>${esc(project)}</span>${modes.map(mode=>`<span class="b-mode ${mode==='Auto'?'auto':''}" title="Task autonomy${modes.length>1?': mixed within this project':''}">${esc(mode.toLowerCase())}</span>`).join('')}</div>${tasks.map(t=>isAttention(t)?`<button class="b-nav-task b-project-pointer" data-open="${t.id}">${esc(t.title)} · in Needs you</button>`:bNavRow(t)).join('')}${tasks.filter(t=>t.id===selected).map(t=>`<div class="b-substeps">${t.steps.map((s,i)=>`<button data-b-task="${t.id}" data-b-step="${i+1}" aria-current="${view==='task'&&panel==='step'&&viewedStep===i+1}"><span class="b-step-cell ${s.status==='Completed'?'complete':s.status==='Running'?'live':''}" aria-hidden="true"></span><span class="mono">${String(i+1).padStart(2,'0')}</span><span>${esc(s.kind)} · ${esc(s.status)}</span></button>`).join('')}</div>`).join('')}${project==='Paper Kite Docs'?'<button class="b-nav-task observed" data-view="observed"><span class="b-nav-title">Compare offline search libraries</span><span class="b-nav-meta"><span class="b-source">VS Code</span>Observed · read-only</span></button>':''}</section>`;
  }).join('')}</div><div class="b-dock-footer"><button class="btn" data-view="new">New task</button></div></aside>`;
}
function bModePicker(t){
  return `<div class="b-levels" role="group" aria-label="Task autonomy"><button data-b-action="rules" title="Review autonomy and approval rules">Rules</button>${['Gated','Suggest','Auto'].map(mode=>`<button data-b-mode="${mode}" aria-pressed="${t.mode===mode}" title="${mode==='Auto'?'Future eligible steps may proceed within existing limits. Pending decisions still require you.':mode==='Suggest'?'Review proposed additional work before it starts.':'Confirm the plan and reserved actions before progression.'}">${mode.toLowerCase()}</button>`).join('')}</div>`;
}
function bTaskHeader(t){
  return `<header class="task-head"><div class="b-breadcrumb"><button class="btn" data-b-action="toggle-dock" aria-expanded="${bDock}">Projects</button><button class="btn" data-back>All tasks</button><span class="project">${esc(t.project)} / ${t.number}</span></div><h1 tabindex="-1" id="task-title">${esc(t.title)}</h1><div class="b-task-meta">${badge(t)}${bModePicker(t)}</div></header>`;
}
composer = t => t.status==='planned' ? '<div class="b-locked">Start assigns this task its own orchestrator. No message has been sent.</div>' : baseB.composer({...t,question:null});
proposal = () => '';
overview = t => {
  const template=document.createElement('template');template.innerHTML=baseB.overview(t);
  const inner=template.content.querySelector('.overview>.inner');
  const status=inner.querySelector('.status-note');status.hidden=true;status.querySelectorAll('button').forEach(b=>b.remove());
  const title=inner.querySelector('h2'),goal=inner.querySelector('.brief'),constraints=inner.querySelector('.constraints');
  title.remove();goal.remove();constraints.remove();inner.querySelector('.secondary')?.remove();
  const brief=t.id==='thumbnails'?'Use dimension-aware keys and a bounded cache. Verify eviction and preserve current thumbnail behavior.':t.latest;
  inner.insertAdjacentHTML('afterbegin',`<div class="b-overview-intro"><section class="b-fact-section"><h2>Prompt</h2><details data-fold="${t.id}-b-prompt" ${expanded.has(t.id+'-b-prompt')?'open':''}><summary>${esc(t.goal.length>118?t.goal.slice(0,118)+'…':t.goal)}</summary><p>${esc(t.goal)}</p><button class="btn" data-b-action="copy-prompt">Copy prompt</button></details></section><section class="b-fact-section"><h2>Brief</h2><details data-fold="${t.id}-b-brief" ${expanded.has(t.id+'-b-brief')?'open':''}><summary>${esc(brief.length>108?brief.slice(0,108)+'…':brief)}</summary><p>${esc(brief)}</p><p class="muted">Keep existing behavior outside this change. Current evidence must cover the reviewed revision.</p><div class="b-brief-files"><span>${t.steps.length} currently planned steps</span><span>·</span><span>${t.mode.toLowerCase()} autonomy</span></div></details></section></div>`);
  const rows=inner.querySelectorAll('.step-row');
  if(t.status==='failed')inner.querySelector('[data-criterion="AC2"] small').textContent=t.latest;
  if(rows.length>1)rows[0].insertAdjacentHTML('afterend',`<button class="b-audit" data-b-action="decision"><span class="cell" aria-hidden="true"></span><span><b>Orchestrator</b> · ${t.owner?esc(routeName(t.owner)):'not assigned'}<br>${t.status==='planned'?'Proposed steps. Start has not assigned an owner.':'Selected evidence determines the next useful step.'}</span></button>`);
  return template.innerHTML;
};
function bDecision(t){
  let tag='',title='',why='',actions='',tone='';
  if(t.status==='planned'){tag='Ready to start';title='Review the proposed steps, then assign an orchestrator.';why='Start fixes the eligible model and effort for this task. No worker has started.';actions=bButton('Edit plan','edit-plan')+bButton('Start task','start',true);}
  else if(t.status==='plan-approval'){tag='Plan to confirm';title='The plan is ready. Confirm before the next worker starts.';why='The same orchestrator owns the task. No code worker has started.';actions=bButton('Read plan','read-plan')+bButton('Redo plan','redo-plan')+bButton('Confirm plan','confirm-plan',true);}
  else if(t.status==='question'&&t.question){tag='Your decision · step '+String(t.question.step).padStart(2,'0');title=t.question.text;why=t.answerQueued?'Answer saved. Orchestrator receipt and worker delivery are still separate.':'No notes changed. Choose an answer or write your own to the orchestrator.';actions=t.answerQueued?bButton('View saved answer','show-orchestrator'):bButton('Append notes','answer-append')+bButton('Replace notes','answer-replace')+bButton('Write answer','write-answer',true);}
  else if(t.status==='proposal'){tag='Orchestrator proposes';title='Repair the cancellation race, then verify it again.';why='Step 04 failed. Sonnet repair and Opus verification are proposed; 2 of 6 attempts used.';actions='<button class="btn" data-action="reject">Reject</button><button class="btn" data-b-action="decision">Review reason</button><button class="btn primary" data-action="approve">Approve proposal</button>';}
  else if(t.status==='model-approval'){tag='Worker model hold';title='Fable is unavailable. Choose an eligible verification worker.';why='No connected Fable route has proven worker support in this sample. Opus is eligible; the Astra orchestrator stays assigned.';actions=bButton('Why Fable is unavailable','worker-fable')+bButton('Use Opus worker','worker-opus',true);}
  else if(t.status==='failed'){tag='Failed after repair';tone='bad';title='Verification still fails after one repair attempt.';why='The six-attempt cap is reached. Inspect the failure or prepare a handoff; another retry is unavailable.';actions=bButton('See failure','see-failure')+bButton('Hand off','handoff')+'<button class="btn" disabled title="The existing six-attempt work cap is reached. No retry override is available.">Retry unavailable</button>';}
  else if(t.status==='ready'){tag='Ready for acceptance';tone='good';title='Current verification passed. The result is ready for your review.';why='Ready does not mean accepted. Review the evidence before accepting this task.';actions=bButton('Review evidence','result')+'<button class="btn primary" data-action="accept">Accept result</button>';}
  else if(t.status==='accepted'){tag='Accepted';tone='good';title='You accepted this result.';why='History and evidence remain available. Reopen explicitly to continue with the same owner.';actions=bButton('Review result','result')+'<button class="btn" data-action="reopen">Reopen task</button>';}
  else if(t.status==='held'){tag='Waiting · '+(t.hold.includes('unknown')?'outcome unconfirmed':'progression held');title=t.hold;why='The saved owner and history are retained. No automatic replay or model substitution.';actions=bButton('Inspect recovery','recovery');}
  else if(t.status==='paused'){tag='Paused';title=t.workerRunning?'Progression paused. The current worker is still running.':'Progression paused. Queued guidance is retained.';why='No new step can begin. Resume rechecks the current gates.';actions='<button class="btn" data-action="resume">Resume task</button>';}
  else if(t.status==='stopped'){tag='Stopped';title='Execution ended. History and queued guidance are retained.';why='No automatic retry. Recovery must reconcile the stopped worker and unresolved guidance.';actions='<button class="btn" data-action="recover">Review recovery</button>';}
  if(!tag)return '';
  return `<section class="b-decision ${tone}" aria-label="Task decision"><div class="b-decision-tag">${tag}</div><div><h2>${esc(title)}</h2><p>${esc(why)}</p></div><div class="b-decision-actions">${actions}</div></section>`;
}
function bActionbar(t){
  const usage=total(state.ledger.filter(r=>r.task===t.number));
  const utility=[['folder','Open project folder'],['terminal','Open in terminal'],['handoff','Prepare handoff'],['trash','Delete task']];
  let actions='';
  if(!['planned','ready','accepted','stopped','failed','paused'].includes(t.status))actions='<button class="btn" data-action="pause">Pause</button>';
  if(!['planned','accepted','stopped','failed','ready'].includes(t.status))actions+='<button class="btn" data-action="stop">Stop</button>';
  if(t.status==='planned')actions+=bButton('Edit prompt','edit-prompt')+bButton('Drop task','delete');
  if(!['planned','accepted'].includes(t.status))actions+='<button class="btn b-message-shortcut" data-message>Message orchestrator</button>';
  return `<div class="b-actionbar" aria-label="Task actions"><div class="b-utility">${utility.map(([key,label])=>`<button class="btn ${key==='trash'?'danger':''}" data-b-action="${key==='trash'?'delete':key}" title="${label}" aria-label="${label}">${bIcon(key)}</button>`).join('')}</div><div class="b-action-usage"><span>${t.workerRunning?'Worker active':esc(stateLabels[t.status])}</span><span class="task-context">Orch ctx ${orchestratorContextGauge(t)}<b>${orchestratorContextLabel(t)}</b></span><span>Task <b>${money(usage.cents)}${usage.unknown?' + unavailable':''}</b></span></div><div class="b-state-actions">${actions}</div></div>`;
}
function bDockHTML(t){return bDecision(t)+bActionbar(t);}
taskView = () => {
  const t=currentTask();if(!t){view='tasks';return tasksView();}
  $('window').dataset.panel=panel;
  const active=panel==='orchestrator'?'overview':panel;
  return `<div class="b-workbench" data-dock-open="${bDock}">${bProjectDock()}<section class="b-task-workspace" aria-label="Selected task">${bTaskHeader(t)}<div class="task-layout"><aside class="orchestrator" aria-label="Task orchestrator conversation"><header class="orchestrator-head"><div class="row spread"><h2>Orchestrator</h2><span class="badge">${t.number}</span></div><p class="identity" data-owner>${t.owner?esc(routeName(t.owner))+' · '+esc(t.effort):'Not assigned · starts after your confirmation'}</p><p class="activity" data-activity>${esc(activityText(t))}</p></header><div class="thread" id="orchestrator-thread" data-scroll="${t.id}-orchestrator" tabindex="0" aria-label="Chronological task conversation"><div data-stream="orchestrator">${t.events.map(e=>eventHTML(e)).join('')}</div></div>${composer(t)}</aside><div class="task-content"><nav class="tabs" role="tablist" aria-label="Task views">${[['orchestrator','Orchestrator'],['overview','Overview'],['step','Step chat'],['context','Context']].map(([id,name])=>`<button role="tab" id="tab-${id}" data-panel="${id}" class="${id==='orchestrator'?'mobile-tab':''}" aria-controls="task-panel" aria-selected="${panel===id}" tabindex="${panel===id?0:-1}">${name}</button>`).join('')}</nav><div class="panel" id="task-panel" role="tabpanel" aria-labelledby="tab-${active}">${active==='overview'?overview(t):active==='step'?stepView(t):contextView(t)}</div></div></div><div class="b-action-dock" aria-label="Persistent task decision and actions">${bDockHTML(t)}</div></section></div>`;
};
const bFiles = t => t.id==='thumbnails'?['src/images/thumbnailCache.ts','tests/thumbnailCache.spec.ts']:t.id==='audio'?['src/export/retry.ts','tests/export-retry-limits.spec.ts']:t.id==='import'?['src/import/mergeCustomerNotes.ts']:['step-'+String(viewedStep).padStart(2,'0')+'/handoff.md','step-'+String(viewedStep).padStart(2,'0')+'/verdict.md'];
stepView = t => {
  const template=document.createElement('template');template.innerHTML=baseB.stepView(t);
  const section=template.content.firstElementChild,s=t.steps[viewedStep-1],future=['Planned','Queued'].includes(s.status);
  section.insertAdjacentHTML('afterbegin',`<div class="b-stepbar"><button class="btn" data-panel="overview">Back to task overview</button><div class="b-stepnav"><button class="btn" data-b-prev ${viewedStep===1?'disabled':''} aria-label="Previous step">‹</button><button class="btn" data-b-next ${viewedStep===t.steps.length?'disabled':''} aria-label="Next step">›</button></div></div>`);
  const header=section.querySelector('.step-header');
  header.insertAdjacentHTML('afterend',`<nav class="b-file-tabs" aria-label="Step artifacts">${[['chat','Chat'],['received','Received'],['handoff','Handoff'],['files','Files']].map(([key,label])=>`<button data-b-file-tab="${key}" aria-pressed="${bStepTab===key}">${label}</button>`).join('')}</nav>`);
  if(bStepTab!=='chat'){
    const body=section.querySelector('.step-transcript');body.className='b-step-artifact';body.removeAttribute('id');body.removeAttribute('tabindex');
    body.dataset.scroll=`${t.id}-step-${viewedStep}-${bStepTab}`;
    if(bStepTab==='received')body.innerHTML=`<h3>${future?'Planned assignment · not delivered':'Received assignment'}</h3><p>${future?'No worker has received this assignment.':'Selected task evidence was sent to this worker, separately from the orchestrator conversation.'}</p><pre>${esc('Goal\n'+s.name+'\n\nTask constraints\n'+t.goal+'\n\nEvidence\nSelected task facts and accepted prior handoff only.\nNo full worker transcript inheritance.')}</pre>`;
    else if(bStepTab==='handoff')body.innerHTML=['Completed','Failed'].includes(s.status)?`<h3>Saved step handoff</h3><pre>${esc('Goal\n'+s.name+'\n\nFindings\n'+(s.status==='Failed'?'Verification failed. No accepted result.':t.latest)+'\n\nFiles touched\n'+bFiles(t).join('\n')+'\n\nTroubleshooting\nOriginal diagnostics retained in step evidence.\n\nOpen questions\n'+t.criteria.filter(c=>c.status!=='Passed').map(c=>c.text).join('\n')+'\n\nNext\nReview current acceptance evidence before further work.')}</pre>`:'<h3>No saved handoff yet</h3><p>This worker has not completed. Its result and verification cannot be inferred from a running or queued process.</p>';
    else body.innerHTML=`<h3>${future?'Proposed files':'Sample file references'}</h3><p>Illustrative paths for this step. The mockup does not read the working tree or claim a live diff.</p>${bFiles(t).map(file=>`<div class="b-file-row"><code>${esc(file)}</code><button class="btn" data-b-file="${esc(file)}">Inspect</button></div>`).join('')}`;
  }
  return template.innerHTML;
};
const baseObservedB=observedView;
observedView = () => `<div class="b-workbench" data-dock-open="${bDock}">${bProjectDock()}<section class="b-task-workspace"><div class="b-stepbar"><button class="btn" data-b-action="toggle-dock" aria-expanded="${bDock}">Projects</button><span class="b-mode">VS Code · observed</span></div>${baseObservedB()}<div class="b-action-dock"><section class="b-decision"><div class="b-decision-tag">Observed · read-only</div><div><h2>Continue in a new Console task when you need controls here.</h2><p>The original VS Code session remains separate. A fork gets a new task and its own assigned orchestrator.</p></div><div class="b-decision-actions">${bButton('Continue as fork','fork-continue',true)}</div></section><div class="b-actionbar">${bButton('Verify as fork','fork-verify')}${bButton('Escalate as fork','fork-escalate')}${bButton('Hand off','observed-handoff')}${bButton('Open in terminal','observed-terminal')}</div></div></section></div>`;
card = t => {
  if(!['planned','plan-approval','model-approval','failed'].includes(t.status))return baseB.card(t);
  return `<article class="live-tile" data-card="${t.id}"><header class="tile-head"><div class="row spread tile-project"><span>${esc(t.project)}</span><span class="mono">${t.number}</span></div><h3><button class="task-title" data-open="${t.id}">${esc(t.title)}</button></h3>${badge(t)}<p class="tile-owner">Orchestrator: ${esc(routeName(t.owner))}</p></header><div class="tile-decision"><h4>${esc(stateLabels[t.status])}</h4><p>${esc(t.hold||t.latest)}</p></div><footer class="tile-footer"><button class="btn" data-open="${t.id}">Review task</button></footer></article>`;
};
render = () => {
  baseB.render();
  $('window').dataset.view=view;
  document.querySelector('.chrome-title').textContent=view==='observed'?'Observed':view==='task'?'Task workspace':'Tasks';
};
setScenario = id => {
  bStepTab='chat';
  if(!Object.hasOwn(bScenarios,id)){baseB.setScenario(id);return;}
  baseB.setScenario('default');state.scenario=id;$('scenario').value=id;
  if(id==='observed'){navigate('observed');return;}
  const t=state.tasks.find(t=>t.id==='thumbnails');t.workerRunning=false;t.hold='';
  t.steps.forEach((s,i)=>{s.events=null;s.status=i<2?'Completed':'Planned';});
  t.status=id==='planned'?'planned':id==='failed-twice'?'failed':id;
  if(id==='planned'){
    t.owner=null;t.effort=null;t.current=1;t.session='Not started';t.orchestratorContextTokens=null;t.checkpoint=0;
    t.steps.forEach(s=>s.status='Planned');t.criteria.forEach(c=>c.status='Not checked');
    t.events=t.events.filter(e=>e.who==='user');state.ledger=state.ledger.filter(r=>r.task!==t.number);
    t.latest='Proposed task plan. Start assigns its orchestrator; no work has begun.';
  }else if(id==='plan-approval'){
    t.current=3;t.latest='The orchestrator prepared the plan. The code worker waits for your confirmation.';
    event(t,'orchestrator',t.latest,{label:'Plan ready · Astra / Codex'});
  }else if(id==='model-approval'){
    t.current=4;t.steps[2].status='Completed';t.steps[3].status='Waiting for approval';
    t.latest='Verification requested the scarce Fable worker route. Approval is held; Opus is the eligible alternative.';
    event(t,'orchestrator',t.latest,{label:'Worker approval · owner unchanged'});
  }else{
    t.current=4;t.steps[2].status='Completed';t.steps[3].status='Failed';
    t.criteria[1].status='Failed';t.hold='Six of six attempts used. No retry or cap override is available.';
    t.latest='Eviction verification still fails after a repair attempt. The original diagnostics are retained.';
    t.steps[3].events=[{id:'failure-assignment',seq:1,who:'user',label:'Assignment · step 04',text:'Verify thumbnail eviction and preserve requested image dimensions.'},{id:'failure-tool',seq:2,who:'tool',tool:true,label:'Test · failed after repair',text:'npm test -- thumbnailCache --run',result:'FAIL: retained entries exceed the configured bound.\nThe previous repair did not resolve eviction. Six of six attempts used.'},{id:'failure-result',seq:3,who:'worker',label:'Verification result',text:t.latest}];
    event(t,'orchestrator',t.latest,{label:'Failed after repair · bounded recovery'});
  }
  navigate('task',{task:t.id});
};
advance = () => {
  baseB.advance();
  const t=currentTask();
  if(view==='task'&&t){
    if(t.bStartPending){delete t.bStartPending;t.status='running';t.workerRunning=true;t.current=1;t.steps[0].status='Running';event(t,'receipt','Initial decision completed. Step 01 assigned to '+routeName(t.steps[0].route)+'.');render();}
    else{
      const dock=document.querySelector('.b-action-dock');if(dock)dock.innerHTML=bDockHTML(t);
      const nav=document.querySelector('.b-project-dock');
      if(nav){
        const template=document.createElement('template');template.innerHTML=bProjectDock();
        if(nav.innerHTML!==template.content.firstElementChild.innerHTML){
          const focused=nav.contains(document.activeElement)?document.activeElement:null;
          nav.querySelectorAll('[data-scroll]').forEach(el=>positions[el.dataset.scroll]=el.scrollTop);
          const focusKey=focused?.dataset.open,stepKey=focused?.dataset.bStep;
          nav.replaceWith(template.content);restorePositions();
          if(focused)document.querySelector(stepKey?'[data-b-step="'+stepKey+'"]':focusKey?'.b-project-dock [data-open="'+focusKey+'"]':'.b-dock-heading button')?.focus({preventScroll:true});
        }
      }
    }
  }
};
function bRefresh(){savePositions();render();}
const baseArtifactB=artifact;
artifact = id => {
  const t=currentTask();
  if(t?.status==='failed'&&id.startsWith('AC')){
    const criterion=t.criteria.find(c=>c.id===id);if(!criterion)return;
    inspect(t.number+' / '+criterion.id,`<pre>${esc(criterion.text+'\nState: '+criterion.status+'\nSource: step 04 / verdict.md\n'+(criterion.status==='Failed'?t.latest:'Checked against '+criterion.basis))}</pre>`);return;
  }
  baseArtifactB(id);
};
function bInspectPlan(t,edit=false){
  const plan=t.steps.map((s,i)=>String(i+1).padStart(2,'0')+' · '+s.name).join('\n');
  inspect(edit?'Edit proposed steps':'Current task plan',edit?`<p class="small muted">One goal per line. These are proposed steps; the orchestrator can adapt them to evidence.</p><form id="b-plan-form"><label class="sr" for="b-plan">Proposed step goals</label><textarea id="b-plan" rows="7" maxlength="4000" required style="width:100%;margin-top:12px">${esc(t.steps.map(s=>s.name).join('\n'))}</textarea><button class="btn ink" type="submit" style="margin-top:10px">Save proposed steps</button></form>`:`<pre>${esc(plan)}</pre><p class="small muted">These are the currently planned steps, not a mandatory pipeline. The same orchestrator chooses further work from evidence.</p>`);
}
function bAction(action){
  const t=currentTask();
  if(action==='toggle-dock'){savePositions();bDock=!bDock;render();document.querySelector(bDock?'.b-dock-heading button':'.b-breadcrumb button,.b-stepbar button')?.focus({preventScroll:true});return;}
  if(action.startsWith('fork-')){
    const kind=action.slice(5),goal={continue:'Continue the offline search comparison in a new task.',verify:'Verify the saved offline search comparison in a new task.',escalate:'Review unresolved offline search questions with a stronger worker in a new task.'}[kind];
    state.newDraft={project:'Paper Kite Docs',goal,criteria:'Review the selected external handoff before choosing further work.',route:'auto'};
    navigate('new');notify('Fork prepared as a new-task draft. Start assigns its own orchestrator. No external session was resumed or transcript imported.');return;
  }
  if(action.startsWith('observed-')){inspect(action==='observed-handoff'?'Observed-session handoff':'Open observed session in terminal','<p>This standalone mockup cannot read external handoffs or launch the original VS Code session. Use the original app. No new run or export was started.</p>');return;}
  if(!t)return;
  if(action==='rules'){
    inspect('Task autonomy and approval rules',`<p>Current task mode: ${esc(t.mode)}.</p><p><strong>Gated:</strong> confirm the plan and reserved actions. <strong>Suggest:</strong> review proposed additional work. <strong>Auto:</strong> eligible future steps may proceed within the existing limits.</p><p class="small muted">Pending questions, plan confirmations, scarce-model approval and final acceptance remain explicit. Mode changes do not replay uncertain actions, increase caps or change the assigned orchestrator.</p>`);return;
  }
  if(action==='edit-prompt'&&t.status==='planned'){
    inspect('Edit task prompt',`<form id="b-prompt-form"><label for="b-prompt">Original task goal</label><textarea id="b-prompt" rows="6" maxlength="4000" required style="width:100%;margin-top:8px">${esc(t.goal)}</textarea><button class="btn ink" type="submit" style="margin-top:10px">Save prompt</button></form>`);return;
  }
  if(action==='start'&&t.status==='planned'){
    const owner=assignment();if(!owner){notify('Start unavailable: no eligible connected orchestration route. Your plan is retained.');return;}
    t.owner=owner;t.effort=resolvedEffort(owner,state.effort);t.status='deciding';t.session=t.id+'-decision-01';t.checkpoint=1;t.bStartPending=true;
    t.latest='Assignment saved. Orchestrator is choosing the first useful worker step.';
    event(t,'receipt','Assigned '+routeName(owner)+' · '+t.effort+'. Ownership stays fixed for this task.');
  }else if(action==='confirm-plan'&&t.status==='plan-approval'){
    t.status='running';t.workerRunning=true;t.steps[t.current-1].status='Running';t.latest='Plan explicitly confirmed. Step 03 worker started.';event(t,'user','Confirmed the current plan.');event(t,'receipt',t.latest);
  }else if(action==='redo-plan'&&t.status==='plan-approval'){
    t.status='deciding';t.latest='Plan revision requested. No worker was started.';event(t,'user','Revise the proposed plan before starting code work.');
  }else if(action==='worker-opus'||action==='worker-fable'){
    if(t.status!=='model-approval')return;
    if(action==='worker-fable'){
      // shortcut: Fable has no proven eligible fixture route; wire real capability and approval gates before allowing launch.
      inspect('Fable worker is unavailable','<p>Fable is a legacy scarce-model example from 52-B. This sample has no connected Fable route with proven worker support. Approval cannot launch an unavailable route.</p><p class="muted small">Use the eligible Opus worker or leave the task held. The Astra orchestrator is retained.</p>');return;
    }
    t.steps[t.current-1].route='opus';t.steps[t.current-1].status='Running';t.status='running';t.workerRunning=true;t.latest='You selected the eligible Opus verification worker. Astra / Codex remains the orchestrator.';event(t,'user',t.latest);
  }else if(action==='answer-append'||action==='answer-replace'){
    t.draft=action==='answer-append'?'Append the imported notes and keep all existing notes.':'Replace the existing notes with imported notes.';focusComposer();send();bRefresh();return;
  }else if(action==='write-answer'||action==='show-orchestrator'){focusComposer();return;
  }else if(action==='read-plan'||action==='edit-plan'){bInspectPlan(t,action==='edit-plan'&&t.status==='planned');return;
  }else if(action==='see-failure'){viewedStep=t.current;bStepTab='chat';changePanel('step');return;
  }else if(action==='result'){changePanel('overview');document.querySelector('.criteria')?.scrollIntoView({block:'start'});return;
  }else if(action==='decision'){
    inspect('Orchestrator decision · '+t.number,`<p>${esc(t.latest)}</p><p class="small muted" style="margin-top:10px">${esc(routeName(t.owner))} · ${t.effort||'unassigned'} · this task only. Evidence: current acceptance criteria and selected step results. No cross-project model conversation.</p>`);return;
  }else if(action==='recovery'){
    inspect('Progression held · '+t.number,`<p>${esc(t.hold)}</p><p class="small muted" style="margin-top:10px">${t.hold.includes('disconnected')?'Change the sample Connections control to reconnect the saved CLI.':t.hold.includes('unknown')?'Reconcile the recorded action outcome in the service before any retry. The mockup has no live receipt to resolve.':'Review the retained task evidence. The mockup cannot publish a checkpoint, raise work limits or prove a live recovery.'}</p>`);return;
  }else if(action==='handoff'){
    inspect('Prepare task handoff · '+t.number,`<p>Review the document before exporting it. Preparing a handoff starts no work and does not mark the task accepted.</p><pre>${esc('Goal\n'+t.goal+'\n\nFindings\n'+t.latest+'\n\nFiles touched\nSee the selected step file references.\n\nTroubleshooting\n'+(t.hold||'Saved task evidence retained.')+'\n\nOpen questions\n'+t.criteria.filter(c=>c.status!=='Passed').map(c=>c.text).join('\n')+'\n\nNext\nReview unmet acceptance criteria with the receiving agent.')}</pre><p class="small muted">Document preview only. Export and linked follow-up creation need the runtime handoff endpoint.</p>`);return;
  }else if(action==='folder'||action==='terminal'){
    inspect(action==='folder'?'Open project folder':'Open in terminal',`<p>Project: ${esc(t.project)}</p><p class="small muted" style="margin-top:10px">${action==='folder'?'Opening Explorer':'Launching a terminal'} needs the desktop bridge. This file-only mockup cannot launch local applications. No session was resumed and no command was run.</p>`);return;
  }else if(action==='delete'){
    if(t.workerRunning||!['planned','stopped','accepted'].includes(t.status)){inspect('Delete is unavailable','<p>Stop active execution and resolve any queued or unconfirmed guidance before deleting a task. History remains available.</p>');return;}
    if(state.pending.some(p=>p.task===t.id&&p.phase<2)||t.events.some(e=>e.delivery==='Queued')){inspect('Unresolved guidance','<p>Queued guidance remains saved. This mockup cannot discard it through deletion. Resolve it through task recovery first.</p>');return;}
    inspect('Delete '+t.number+'?',`<p>Remove this task from the local sample only. Reset restores it. Recorded shared usage remains in the ledger.</p><button class="btn" data-b-action="confirm-delete" style="margin-top:12px">Delete sample task</button>`);return;
  }else if(action==='confirm-delete'){
    state.tasks=state.tasks.filter(item=>item.id!==t.id);$('inspector').close();selected=null;navigate('tasks');return;
  }else if(action==='copy-prompt'){
    if(navigator.clipboard)navigator.clipboard.writeText(t.goal).then(()=>notify('Prompt copied.'),()=>inspect('Copy prompt','<pre>'+esc(t.goal)+'</pre>'));
    else inspect('Copy prompt','<pre>'+esc(t.goal)+'</pre>');return;
  }else return;
  bRefresh();
}
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.bAction){bAction(b.dataset.bAction);return;}
  if(b.dataset.bMode){const t=currentTask();if(!t)return;t.mode=b.dataset.bMode;event(t,'user','Changed task autonomy to '+t.mode+'. Pending decisions and reserved approvals remain explicit.');bRefresh();return;}
  if(b.hasAttribute('data-b-prev')||b.hasAttribute('data-b-next')){viewedStep+=b.hasAttribute('data-b-next')?1:-1;bStepTab='chat';bRefresh();document.querySelector(b.hasAttribute('data-b-next')?'[data-b-next]':'[data-b-prev]')?.focus({preventScroll:true});return;}
  if(b.dataset.bFileTab){bStepTab=b.dataset.bFileTab;bRefresh();document.querySelector('[data-b-file-tab="'+bStepTab+'"]')?.focus({preventScroll:true});return;}
  if(b.dataset.bStep){bStepTab='chat';navigate('task',{task:b.dataset.bTask,step:Number(b.dataset.bStep),panel:'step'});if($('window').clientWidth<=1050){bDock=false;bRefresh();}return;}
  if(b.dataset.bFile){inspect('Sample file reference','<pre>'+esc(b.dataset.bFile)+'</pre><p class="small muted">This is an illustrative path. No repository read or live diff is available in the standalone mockup.</p>');}
},false);
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.open||b.dataset.stepOpen){bStepTab='chat';if($('window').clientWidth<=1050)bDock=false;}
},true);
document.addEventListener('submit',e=>{
  if(e.target.id==='b-prompt-form'){
    e.preventDefault();const t=currentTask(),goal=$('b-prompt').value.trim();if(!goal||t.status!=='planned')return;
    t.goal=goal;t.events.find(item=>item.who==='user').text=goal;$('inspector').close();bRefresh();return;
  }
  if(e.target.id!=='b-plan-form')return;e.preventDefault();
  const names=$('b-plan').value.split('\n').map(name=>name.trim()).filter(Boolean);
  if(!names.length){$('b-plan').setCustomValidity('Add at least one proposed step.');$('b-plan').reportValidity();return;}
  const t=currentTask();if(t.status!=='planned')return;
  t.steps=names.map(name=>({name,kind:'Proposed',route:'sonnet',status:'Planned'}));t.current=1;$('inspector').close();bRefresh();
});
document.addEventListener('change',e=>{if(e.target.id==='step-select')bStepTab='chat';},true);
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&!$('inspector').open){
    if(bDock&&$('window').clientWidth<=1050){bDock=false;bRefresh();document.querySelector('[data-b-action="toggle-dock"]')?.focus();}
    else if(view==='task'&&panel==='step'){bStepTab='chat';changePanel('overview');}
  }
});
$('advance').onclick=()=>advance();
$('scenario').innerHTML=Object.entries(scenarioNames).map(([id,name])=>`<option value="${id}">${name}</option>`).join('');
const bParams=new URLSearchParams(location.search),bScenario=bParams.get('scenario');
setScenario(Object.hasOwn(scenarioNames,bScenario)?bScenario:'default');
if(['tasks','new','settings','usage','observed'].includes(bParams.get('view')))navigate(bParams.get('view'));
else if(bParams.get('view')==='task'&&state.tasks.some(t=>t.id===bParams.get('task'))){
  const t=state.tasks.find(t=>t.id===bParams.get('task')),n=Number(bParams.get('step'));
  navigate('task',{task:t.id,panel:['overview','step','context','orchestrator'].includes(bParams.get('panel'))?bParams.get('panel'):undefined,step:Number.isInteger(n)&&n>0&&n<=t.steps.length?n:t.current});
}else if(!bParams.has('view')&&!bParams.has('scenario'))navigate('task',{task:'thumbnails'});
if(bParams.get('dock')==='closed'){bDock=false;render();}
if(bParams.get('stream')==='playing')setPlaying(true);
$('task-title')?.blur();
// shortcut: Version B shares Version A's local fixture engine; runtime integration needs service-derived actions, receipts and capability gates.
