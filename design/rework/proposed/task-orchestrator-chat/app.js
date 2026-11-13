'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = cents => '$' + (cents / 100).toFixed(2);
const number = n => n.toLocaleString('en-US');
const routeInfo = {
  astra:{id:'codex:gpt-6-astra',model:'Astra',cli:'Codex'},
  opus:{id:'claude:opus',model:'Opus',cli:'Claude Code'},
  sonnet:{id:'claude:sonnet',model:'Sonnet',cli:'Claude Code'}
};
const scenarioNames = {
  default:'Six-task overview', 'worker-running':'Worker running', question:'Question', proposal:'Repair proposal', ready:'Ready for acceptance', accepted:'Accepted',
  'cli-unavailable':'Owner disconnected', 'rate-limited':'Owner rate limited', renewal:'Context renewal', 'checkpoint-error':'Checkpoint save failed',
  'context-overflow':'Required context overflow', uncertain:'Uncertain dispatch', 'budget-hold':'Existing budget hold', paused:'Paused with guidance',
  stopped:'Stopped', capacity:'Waiting for capacity', 'unknown-usage':'Unknown usage', 'no-eligible-cli':'No eligible CLI', empty:'Empty tasks',
  loading:'Loading snapshot', offline:'Snapshot unavailable', 'long-content':'Long content', 'stale-verification':'Stale verification', 'delivery-uncertain':'Uncertain delivery'
};
const stateLabels = {question:'Needs your reply',proposal:'Needs approval',running:'Worker running',ready:'Ready for your acceptance',accepted:'Accepted',paused:'Paused',stopped:'Stopped',held:'Waiting',capacity:'Waiting for capacity',deciding:'Orchestrator deciding'};
const holdReasons = {
  'cli-unavailable':'Codex is disconnected. This task keeps Astra / Codex and waits for its owner to reconnect.',
  'rate-limited':'The assigned Astra / Codex route is rate limited. Reset time is unavailable. No fallback is assigned.',
  'checkpoint-error':'Checkpoint publication failed. The previous valid checkpoint (revision 7) is retained. Progression is held.',
  'context-overflow':'Required goal, constraints and acceptance content exceed the 32 KiB initial packet bound. No requirements were cut. A bounded scope or plan split is needed.',
  uncertain:'Action outcome unknown. The worker launch intent has no confirmed outcome. Dispatch is held; it will not be replayed automatically.',
  'budget-hold':'Existing task work cap reached: 6 of 6 permitted worker attempts. No override or additional work is available.'
};
const taskSeeds = [
  ['import','T-017','Fieldnotes CRM','Keep customer notes on import','opus','question',3,'Gated',['Inspect import format','Map customer fields','Resolve duplicate notes','Import sample','Verify records'],'Duplicate matching is ready. No notes will be changed before your decision.'],
  ['audio','T-024','Waveform Studio','Retry interrupted audio exports','opus','proposal',4,'Suggest',['Trace export timeout','Add bounded retry','Exercise cancellation','Verify retry limits'],'The first verification found a cancellation race. A focused repair needs approval.'],
  ['thumbnails','T-031','Catalog Atlas','Cache product thumbnails','astra','running',3,'Auto',['Inspect image loader','Define cache key','Implement cache','Verify eviction','Record results'],'Cache keys include the requested size. Bounded eviction is being implemented.'],
  ['captions','T-038','Frame Orchard','Preserve speaker names in captions','opus','running',2,'Auto',['Read caption schema','Add speaker mapping','Verify round trip','Write handoff'],'The worker is running quietly. Silence alone does not establish failure.'],
  ['search','T-033','Harbor Reader','Add keyboard search','astra','running',2,'Auto',['Audit shortcuts','Build search entry','Wire results','Verify keyboard flow'],'Keyboard search opens. The worker is checking focus return to the reader.'],
  ['archive','T-012','Ledger Grove','Export invoice archive','opus','ready',4,'Gated',['Read export format','Build archive','Verify manifest','Write handoff'],'Current verification passed. Review the archive before accepting it.']
];
const goals = {
  import:'Import the sample customer records. Ask how to merge notes when a customer already exists.',
  audio:'Retry interrupted audio exports within the existing retry limit, and stop retries when an export is cancelled.',
  thumbnails:'Implement a bounded thumbnail cache. Preserve the requested image dimensions and existing thumbnail behavior.',
  captions:'Carry speaker names through parsing and export, then verify the caption round trip.',
  search:'Add keyboard search and return focus to the reader after search closes.',
  archive:'Prepare the invoice archive and manifest. Verify that every sample invoice is accounted for.'
};
const criterionSeeds = {
  thumbnails:[['Requested dimensions remain distinct in the cache key.','Passed'],['Cache retention is bounded and eviction works.','Not checked'],['Existing thumbnail behavior passes relevant regression checks.','Not checked']],
  import:[['The duplicate-note rule is explicitly chosen by you.','Not checked'],['Existing notes remain intact according to that rule.','Not checked']],
  audio:[['Cancelled exports do not retry.','Failed'],['The existing retry limit is respected.','Passed']],
  captions:[['Speaker names survive the export round trip.','Not checked']],
  search:[['Search opens from the keyboard and returns focus on close.','Not checked']],
  archive:[['All 24 sample invoices are in the archive.','Passed'],['The manifest matches every archive entry.','Passed']]
};
// Independent sample worker-context readings from the operator reference; these are not cumulative usage.
const workerContextReadings={import:84000,audio:186000,thumbnails:72000,captions:132000,search:null,archive:26000};
const orchestratorContextEstimates={import:4800,audio:5200,thumbnails:6400,captions:3100,search:null,archive:2700};
const ledgerSeeds = [
 ['u01','T-017','orchestrator','Opus',18000,24],['u02','T-017','worker','Sonnet',36000,18],
 ['u03','T-024','orchestrator','Opus',22000,30],['u04','T-024','worker','Sonnet',48000,24],['u05','T-024','worker','Opus',30000,42],
 ['u06','T-031','orchestrator','Astra',21000,18],['u07','T-031','worker','Sonnet',63000,31],
 ['u08','T-038','orchestrator','Opus',12000,16],['u09','T-038','worker','Sonnet',27000,14],
 ['u10','T-033','orchestrator','Astra',15000,12],['u11','T-033','worker','Astra',33000,26],
 ['u12','T-012','orchestrator','Opus',16000,22],['u13','T-012','worker','Sonnet',40000,20],
 ['u14',null,'other','Opus',10000,14],['u15',null,'other','Astra',9000,7]
];
let state, view = 'tasks', selected = null, panel = 'overview', viewedStep = 3, playing = false, timer, homeFocus = null, dialogReturn;
let positions = {}, expanded = new Set();
function event(t, who, text, extra = {}) {
  const e = {id:'e'+(++t.sequence),seq:t.sequence,tick:state.tick,who,text,...extra};
  t.events.push(e); return e;
}
function baseState() {
  state = {tasks:[],ledger:ledgerSeeds.map(([id,task,role,model,tokens,cents]) => ({id,task,role,model,tokens,cents})),effort:'high',scenario:'default',connections:'default',activity:'snapshot',tick:0,newDraft:{project:'Catalog Atlas',goal:'',criteria:'',route:'auto'},pending:[],renewed:false,projectScope:'all',gridFilter:'all',following:{}};
  state.tasks = taskSeeds.map(([id,number,project,title,owner,status,current,mode,names,latest]) => {
    const worker = id === 'search' ? 'astra' : id === 'archive' || id === 'audio' ? 'opus' : 'sonnet';
    const t = {id,number,project,title,owner,effort:'high',status,current,mode,latest,draft:'',sequence:0,events:[],goal:goals[id],session:id+'-decision-07',orchestratorContextTokens:orchestratorContextEstimates[id],checkpoint:7,hold:'',workerRunning:status==='running',
      criteria:criterionSeeds[id].map(([text,status],i) => ({id:'AC'+(i+1),text,status,basis:'sample revision 7'})),
      steps:names.map((name,i) => ({name,kind:/Inspect|Read|Trace|Audit/.test(name)?'Scout':/Verify|Exercise/.test(name)?'Verify':/Record|Document|handoff/.test(name)?'Explain':'Code',route:i+1===current?worker:'sonnet',contextTokens:i+1===current?workerContextReadings[id]:null,status:i+1<current||status==='ready'?'Completed':i+1===current?status==='running'?'Running':status==='question'?'Waiting for answer':status==='proposal'?'Failed':'Completed':'Planned'}))};
    event(t,'user',t.goal,{label:'You · original goal'});
    event(t,'orchestrator',id==='thumbnails'?'The scout found an unbounded cache. Step 03 will add size-aware keys and eviction; the retention criterion still needs evidence.':'I will choose the next useful step from this task’s acceptance criteria and saved evidence.',{label:'Orchestrator · '+routeInfo[owner].model});
    event(t,'tool','Reviewed selected task evidence.',{tool:true,label:'Read selected evidence',result:'Included: original goal, saved decisions and accepted handoff. Worker transcripts are not included.'});
    if (t.workerRunning) event(t,'receipt','Assigned step '+String(current).padStart(2,'0')+' to '+routeInfo[worker].model+' / '+routeInfo[worker].cli+'. Waiting for worker result.',{step:current});
    if(id==='import') {t.question={id:'notes-step-3',step:3,text:'When a customer already has notes, should the imported notes replace them or be appended?'};event(t,'orchestrator',t.question.text,{label:'Question · source step 03',question:t.question.id});}
    if(id==='audio') event(t,'orchestrator','Step 04 verification received: cancellation can race with retry scheduling. Propose a focused code repair, then fresh verification. This stays within the existing cap (2 of 6 attempts used).',{label:'Evidence review · step 04'});
    if(id==='archive') event(t,'orchestrator','Current manifest evidence covers all 24 sample invoices. The result is ready for your acceptance.',{label:'Evidence review · step 04'});
    return t;
  });
}
function currentTask(){return state.tasks.find(t => t.id === selected);}
function total(records = state.ledger) {
  return records.reduce((a,r) => ({tokens:a.tokens+(r.tokens??0),cents:a.cents+(r.cents??0),unknown:a.unknown+Number(r.tokens===null||r.cents===null)}),{tokens:0,cents:0,unknown:0});
}
function addUsage(record){if(!state.ledger.some(r=>r.id===record.id))state.ledger.push(record);}
function isAttention(t){return ['question','proposal','ready'].includes(t.status);}
function routeName(key){const r=routeInfo[key];return (r.display||r.model)+' / '+r.cli;}
function activityText(t){const why=routeExclusion(t.owner);return why?why+(t.workerRunning?' Existing worker can continue; the next decision waits.':' The saved owner waits.'):t.status==='running'?'Waiting for worker result':t.status==='held'?t.hold:t.status==='paused'?'Paused. No new step can begin.':t.status==='accepted'?'Accepted. Reopen to continue.':t.status==='capacity'?'Waiting for worker capacity; no worker is running.':t.status==='deciding'?'Reviewing unmet acceptance criteria':stateLabels[t.status];}
function routeExclusion(key) {
  if(state.connections==='none')return 'No connected, enabled CLI with proven orchestration tools is available.';
  if(key==='astra'&&state.connections==='codex-off')return 'Codex is disconnected.';
  return '';
}
function assignment() {
  const eligible=['astra','opus'].filter(key=>!routeExclusion(key));
  return eligible.sort((a,b)=> {
    const load = key => state.activity==='idle'?0:state.activity==='astra-active'?Number(key==='astra'):state.tasks.filter(t=>t.owner===key&&t.status==='deciding').length;
    return load(a)-load(b)||total(state.ledger.filter(r=>r.model===routeInfo[a].model)).tokens-total(state.ledger.filter(r=>r.model===routeInfo[b].model)).tokens;
  })[0];
}
function resolvedEffort(owner,effort){return owner==='astra'&&['xhigh','max'].includes(effort)?'high':effort;}
function notify(text){$('feedback').hidden=false;$('feedback').textContent='Simulation: '+text;}
function savePositions(){document.querySelectorAll('[data-scroll]').forEach(e=>positions[e.dataset.scroll]=e.scrollTop);}
function restorePositions(){document.querySelectorAll('[data-scroll]').forEach(e=>{e.scrollTop=positions[e.dataset.scroll]??0;});}
function sequence(t){return '<div class="sequence" aria-label="Currently planned steps">'+t.steps.map((s,i)=>'<i class="'+(s.status==='Completed'?'complete':i+1===t.current?isAttention(t)?'waiting':'current':'')+'" title="'+esc(s.name+': '+s.status)+'"></i>').join('')+'</div><span class="sequence-label">Currently planned · '+t.steps.length+' steps</span>';}
function badge(t){return '<span class="badge '+(isAttention(t)?'attention':t.status==='accepted'?'good':'')+'"><span class="cell" aria-hidden="true"></span>'+esc(stateLabels[t.status])+'</span>';}
function orchestratorContextLabel(t){return t.orchestratorContextTokens==null?'Unavailable':number(t.orchestratorContextTokens/1000)+'k';}
function orchestratorContextGauge(t){
  const tokens=t.orchestratorContextTokens,unknown=tokens==null;
  const semantics=unknown?'role="img" aria-label="Orchestrator context unavailable"':`role="meter" aria-label="Estimated orchestrator context against the sample 300k handoff scale" aria-valuemin="0" aria-valuemax="300000" aria-valuenow="${Math.min(tokens,300000)}" aria-valuetext="${number(tokens)} estimated tokens; sample scale, not a model capacity"`;
  return `<span class="meter-cells context-cells${unknown?' unavailable':''}" ${semantics}>${Array.from({length:15},(_,i)=>`<i aria-hidden="true" style="--fill:${unknown?0:Math.max(0,Math.min(1,tokens/20000-i))*100}%"></i>`).join('')}</span>`;
}
function taskTelemetry(t){
  const context=orchestratorContextLabel(t),usage=total(state.ledger.filter(r=>r.task===t.number));
  return `<span class="task-context" title="Orchestrator context for session ${esc(t.session)}: ${context==='Unavailable'?'Unavailable':'estimated last decision context, '+number(t.orchestratorContextTokens)+' tokens'}. Squares use the operator reference's sample 300k handoff scale. Separate from worker context and archived history.">Orch ctx ${orchestratorContextGauge(t)}<b>${context}${context==='Unavailable'?'':' est.'}</b></span><span class="task-spend" title="Sample estimated total for this task across all orchestrator and worker turns. Included in shared global usage; not an additional charge.">Task <b>${money(usage.cents)}${usage.unknown?' + unavailable':''}</b></span>`;
}
function card(t){
  const action=t.status==='question'?'Answer question':t.status==='proposal'?'Review proposal':t.status==='ready'?'Review result':t.status==='held'?'View reason':t.workerRunning?'Open chat':'Open task';
  const summary=total(state.ledger.filter(r=>r.task===t.number));
  const heading=t.status==='question'?'Append or replace existing notes?':t.status==='proposal'?'Repair the cancellation race?':t.status==='ready'?'Invoice archive ready for review.':stateLabels[t.status];
  const fact=t.status==='question'?'No notes changed':t.status==='proposal'?'Approval required · no repair started':t.status==='ready'?'Current verification passed · awaiting acceptance':t.hold||t.latest;
  const footer=`<div class="tile-telemetry" data-task-telemetry="${t.id}">${taskTelemetry(t)}</div>${t.workerRunning?`<button class="follow-button" data-follow="${t.id}" ${state.following[t.id]!==false?'hidden':''} aria-pressed="${state.following[t.id]!==false}" aria-label="Follow latest worker messages for ${esc(t.title)}">Jump to latest</button>`:''}`;
  const header=`<header class="tile-head">
    <div class="row spread tile-project"><span>${esc(t.project)}</span><span class="mono">${t.number}</span></div>
    <div class="tile-title-row"><h3><button class="task-title" data-open="${t.id}" data-focus="title-${t.id}">${esc(t.title)}</button></h3>
      <details class="tile-details" data-fold="${t.id}-metadata" ${expanded.has(t.id+'-metadata')?'open':''}><summary aria-label="${t.number} task details">Details</summary>
        <div class="tile-details-panel" role="group" tabindex="0" aria-label="${t.number} task metadata"><dl>
          <dt>Orchestrator</dt><dd>${esc(routeName(t.owner))}</dd>
          <dt>Orchestrator context</dt><dd>${orchestratorContextLabel(t)}${t.orchestratorContextTokens==null?'':' tokens · Estimated last decision context'}</dd>
          <dt>Effort</dt><dd>${t.effort}</dd>
          <dt>Worker</dt><dd>${t.workerRunning?esc(routeName(t.steps[t.current-1].route))+' · separate session':'No active worker'}</dd>
          <dt>Worker context</dt><dd>${t.steps[t.current-1].contextTokens==null?'Unavailable':number(t.steps[t.current-1].contextTokens)+' tokens · Measured sample reading'}</dd>
          <dt>Current step</dt><dd>${t.current} of ${t.steps.length} · ${esc(t.steps[t.current-1].name)}</dd>
          <dt>Task usage</dt><dd>${number(summary.tokens)} processed tokens / ${money(summary.cents)} sample estimate${summary.unknown?' known subtotal + unavailable usage':''}</dd>
        </dl><div class="tile-plan">${sequence(t)}</div></div>
      </details>
    </div>
    <div class="tile-caption"><span class="tile-owner">Orchestrator: <b>${esc(routeInfo[t.owner].display||routeInfo[t.owner].model)}</b></span><span class="tile-state ${isAttention(t)?'attention':''}"><span class="cell" aria-hidden="true"></span>${esc(t.id==='captions'&&t.workerRunning?'Running · output quiet':stateLabels[t.status])}</span></div>
  </header>`;
  return `<article class="task-card live-tile ${isAttention(t)?'needs':''}" data-card="${t.id}" aria-label="${esc(t.title)}">${header}${t.workerRunning?`<div class="tile-stream" data-preview-task="${t.id}" data-stream="preview" data-scroll="preview-${t.id}" tabindex="0" aria-label="${esc(t.title)} read-only worker preview"><div>${stepEvents(t,t.current).map(e=>eventHTML(e,t.id+'-preview')).join('')}</div></div>`:`<div class="tile-decision"><h4>${heading}</h4><p>${esc(t.latest)}</p><p class="decision-fact">${esc(fact)}</p></div>`}<footer class="tile-footer">${footer}<button class="btn ${isAttention(t)?'primary':''}" data-open="${t.id}" data-focus="action-${t.id}" ${isAttention(t)&&t.status!=='ready'?'data-reply="true"':''} ${t.workerRunning?'data-open-panel="step"':''}>${action} <svg class="icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13m-5-5 5 5-5 5"/></svg></button></footer></article>`;
}
function usageStrip(){
  const sum=total(),cells=share=>'<span class="meter-cells" aria-hidden="true">'+Array.from({length:32},(_,i)=>'<i class="'+(i<Math.round(share*32)?'filled':'')+'"></i>').join('')+'</span>';
  return `<div class="usage-cost"><span class="usage-amount">${money(sum.cents)}</span><div class="usage-caption"><strong>Today · sample estimated cost</strong><span>${number(sum.tokens)} processed tokens${sum.unknown?' + unavailable':''}</span><small>All projects · orchestration included</small></div></div><div class="usage-models">${['Sonnet','Opus','Astra'].map(model=>{const row=total(state.ledger.filter(r=>r.model===model)),share=sum.tokens?row.tokens/sum.tokens:0;return `<div class="usage-model" data-strip-model="${model}"><div class="row spread"><b>${model}</b><span>${number(row.tokens)}${row.unknown?' + unavailable':''}</span></div>${cells(share)}<small>${(share*100).toFixed(1)}% of known processed tokens</small></div>`;}).join('')}</div><button class="btn link strip-usage" data-view="usage">Usage <span aria-hidden="true">+</span></button>`;
}
function projectRail(){
  const projects=['all',...new Set(state.tasks.map(t=>t.project))];
  return `<aside class="project-rail" aria-label="Projects"><div class="project-head"><h2>Projects</h2><label class="sr" for="project-scope">Filter by project</label><select id="project-scope">${projects.map(p=>`<option value="${esc(p)}" ${state.projectScope===p?'selected':''}>${p==='all'?'All projects':esc(p)}</option>`).join('')}</select></div><nav class="project-list" aria-label="Filter by project">${projects.map(p=>{const tasks=state.tasks.filter(t=>p==='all'||t.project===p),running=tasks.filter(t=>t.workerRunning).length,needs=tasks.filter(isAttention).length;return `<button class="project-item" data-project-scope="${esc(p)}" aria-current="${state.projectScope===p}"><span class="project-name">${p==='all'?'All projects':esc(p)}</span><span class="project-counts">${running?'<span>'+running+' running</span>':''}${needs?'<span class="attention">'+needs+' need you</span>':''}${!running&&!needs?tasks.length+' tasks':''}</span></button>`;}).join('')}</nav><div class="rail-footer"><button class="rail-attention" data-decisions>${state.tasks.filter(isAttention).length} need you<span>Across all projects</span></button><button class="btn" data-view="new">New task</button></div></aside>`;
}
function tasksView(){
  if(['loading','offline','empty'].includes(state.scenario)) {
    const labels={loading:['Loading tasks','The sample snapshot is loading. No task actions are available.','Load sample snapshot'],offline:['Snapshot unavailable','The sample snapshot could not be loaded. Last-known actions are unavailable while offline.','Retry snapshot'],empty:['No tasks yet','Create a task to assign its own orchestrator.','New task']};
    const [title,copy,action]=labels[state.scenario];
    return `<div class="scroll" data-scroll="tasks"><section class="empty"><h1>${title}</h1><p>${copy}</p><button class="btn ink" ${state.scenario==='empty'?'data-view="new"':'data-snapshot="true"'}>${action}</button></section></div>`;
  }
  const scoped=state.tasks.filter(t=>state.projectScope==='all'||t.project===state.projectScope),visible=scoped.filter(t=>state.gridFilter==='all'||state.gridFilter==='running'&&t.workerRunning||state.gridFilter==='needs'&&isAttention(t));
  visible.sort((a,b)=>Number(b.workerRunning)-Number(a.workerRunning));
  return `<div class="operator-board">${projectRail()}<section class="live-workspace" aria-label="Live task grid"><header class="grid-head"><div><h2>Live tasks</h2><p>${state.projectScope==='all'?'All projects':esc(state.projectScope)} · read-only worker previews</p></div><div class="row"><nav class="grid-filters" aria-label="Filter tasks">${[['all','All tasks'],['running','Running'],['needs','Needs you']].map(([key,label])=>`<button data-grid-filter="${key}" aria-pressed="${state.gridFilter===key}">${label} <span ${key==='running'?'data-active':key==='needs'?'data-needs':''}>${scoped.filter(t=>key==='all'||key==='running'&&t.workerRunning||key==='needs'&&isAttention(t)).length}</span></button>`).join('')}</nav><button class="btn" data-grid-play aria-pressed="${playing}">${playing?'Pause streams':'Play streams'}</button><button class="btn" data-decisions>Decision queue <span aria-hidden="true">→</span></button></div></header><div class="scroll grid-scroll" data-scroll="tasks">${visible.length?`<div class="task-grid live-grid">${visible.map(card).join('')}</div>`:'<div class="grid-empty">No tasks in this view.<button class="btn" data-grid-filter="all">Show all tasks</button></div>'}<section class="observed-row"><div><h3>Compare offline search libraries</h3><p>Paper Kite Docs · Observed session · VS Code · read-only</p></div><button class="btn" data-view="observed">Open session</button></section></div></section></div>`;
}
function eventHTML(e,scope=selected){
  if(e.tool)return `<article class="event" data-event="${e.id}" data-seq="${e.seq}"><details class="tool-call" data-fold="${scope}-${e.id}" ${expanded.has(scope+'-'+e.id)?'open':''}><summary>${esc(e.label)}</summary><div class="tool-body"><code>${esc(e.text)}</code><pre>${esc(e.result)}</pre></div></details></article>`;
  return `<article class="event ${e.who==='orchestrator'?'agent':e.who}" data-event="${e.id}" data-seq="${e.seq}" ${e.recipient?'data-recipient="'+esc(e.recipient)+'"':''} ${e.question?'data-question="'+esc(e.question)+'"':''}><div class="speaker">${e.who==='orchestrator'?'<span class="cell" aria-hidden="true"></span>':''}${esc(e.label||(e.who==='user'?'You':e.who==='receipt'?'Task receipt':'Worker'))}</div><p data-field="text">${esc(e.text)}</p>${e.delivery?'<div class="event-meta">'+esc(e.delivery)+'</div>':''}</article>`;
}
function proposal(t){return t.status==='proposal'?`<section class="status-note attention" data-proposal><h3>Focused repair for the cancellation race</h3><p class="small">Step 04 verification failed for the first time: a cancelled export can schedule another retry.</p><p class="small muted">Proposed: code repair on Sonnet, then fresh verification. Existing cap: 2 of 6 attempts used. Orchestrator remains ${esc(routeName(t.owner))}.</p><div class="row" style="margin-top:12px"><button class="btn primary" data-action="approve">Approve proposal</button><button class="btn" data-action="reject">Reject proposal</button></div></section>`:'';}
function composer(t){
  if(t.status==='accepted')return '<div class="composer-closed"><p class="muted">Accepted. Reopen this task before sending more guidance.</p><button class="btn" data-action="reopen">Reopen task</button></div>';
  const question=t.question&&!t.answerQueued;
  return `<form class="composer" id="task-form" data-recipient="${t.number}-orchestrator">${question?`<div class="question" data-question="${esc(t.question.id)}">Step ${String(t.question.step).padStart(2,'0')}: ${esc(t.question.text)}</div><div class="row suggestions"><button class="btn" type="button" data-suggest="Append the imported notes and keep all existing notes.">Append notes</button><button class="btn" type="button" data-suggest="Replace the existing notes with imported notes.">Replace notes</button></div>`:''}<label for="task-draft">To: ${t.number} orchestrator</label><textarea id="task-draft" maxlength="4000" aria-describedby="composer-hint">${esc(t.draft)}</textarea><p class="hint" id="composer-hint">Guidance is saved for this task and delivered at the next safe boundary.</p><div class="row spread"><span class="hint">Enter: newline · Ctrl/⌘+Enter: send</span><button class="btn ink" type="submit">${question?'Send answer':'Send'}</button></div></form>`;
}
function usageSubset(t){const rows=state.ledger.filter(r=>r.task===t.number),sum=total(rows),o=total(rows.filter(r=>r.role==='orchestrator')),w=total(rows.filter(r=>r.role==='worker'));return `<p class="usage-subset" data-task-tokens="${sum.tokens}" data-task-cents="${sum.cents}">${number(sum.tokens)} processed tokens / ${money(sum.cents)} sample estimate${sum.unknown?' known subtotal; '+sum.unknown+' session with unavailable usage':''}</p><p class="hint">Orchestration ${number(o.tokens)} / ${money(o.cents)} · Workers ${number(w.tokens)} / ${money(w.cents)}. Included in global usage.</p>`;}
function overview(t){
  const notes=t.hold||t.latest;
  return `<section class="overview" data-scroll="${t.id}-overview" aria-label="Task overview"><div class="inner"><h2>Goal and constraints</h2><p class="brief" style="margin-top:10px">${esc(t.goal)}</p><p class="constraints">Keep existing behavior outside this change. Current evidence must cover the result being reviewed.</p><section class="status-note ${isAttention(t)||t.hold?'attention':''}"><h3>${esc(stateLabels[t.status])}</h3><p>${esc(notes)}</p><p class="small muted">Orchestrator: ${esc(routeName(t.owner))}${t.workerRunning?'<br>Current worker: '+esc(routeName(t.steps[t.current-1].route))+' · step '+String(t.current).padStart(2,'0'):''}</p>${t.status==='question'?'<button class="btn primary" data-message style="margin-top:10px">Reply to question</button>':''}${t.status==='ready'?'<button class="btn primary" data-action="accept" style="margin-top:10px">Accept result</button>':''}${t.status==='accepted'?'<button class="btn" data-action="reopen" style="margin-top:10px">Reopen task</button>':''}</section><section class="section"><h2>Acceptance criteria</h2><ul class="criteria">${t.criteria.map(c=>`<li class="criterion" data-criterion="${c.id}"><span>${esc(c.text)}</span><span class="state ${c.status==='Passed'?'good':c.status==='Failed'?'bad':''}">${c.status}</span><small>${c.status==='Failed'?'Cancellation raced with retry scheduling. Repair this boundary, then reverify.':c.status==='Needs recheck'?'A later writing change invalidated the current basis; the previous pass remains in history.':c.status==='Passed'?'Checked against '+c.basis:'No current evidence yet.'}</small>${c.status!=='Not checked'?`<button class="btn link" data-artifact="${c.id}">View ${c.status==='Needs recheck'?'previous ':''}evidence</button>`:''}</li>`).join('')}</ul></section><section class="section"><h2>Currently planned steps</h2>${t.steps.map((s,i)=>`<div class="step-row ${i+1===t.current?'current':''}" data-step="${i+1}"><span class="mono muted">${String(i+1).padStart(2,'0')}</span><div><b>${esc(s.name)}</b><p>${s.kind} · ${s.status}${s.status!=='Planned'?' · '+esc(routeName(s.route)):''}</p></div><button class="btn" data-step-open="${i+1}">${s.status==='Planned'?'View planned step':s.status==='Completed'||s.status==='Failed'?'View result':'Open step chat'}</button></div>`).join('')}</section><section class="section"><h2>Task usage</h2>${usageSubset(t)}</section><div class="row secondary">${['accepted','stopped'].includes(t.status)?'':`<button class="btn" data-action="${t.status==='paused'?'resume':'pause'}">${t.status==='paused'?'Resume task':'Pause task'}</button><button class="btn" data-action="stop">Stop task</button>`}${t.status==='stopped'?'<button class="btn" data-action="recover">Review recovery</button>':''}<button class="btn mobile-message" data-message>Message orchestrator</button></div></div></section>`;
}
function stepEvents(t,n){
  const s=t.steps[n-1];
  if(s.status==='Planned'||s.status==='Queued')return [];
  if(s.events)return s.events;
  const events=[{id:'assignment',seq:1,who:'user',label:'Assignment · step '+String(n).padStart(2,'0'),text:s.name+'. '+t.goal},
    {id:'worker-intro',seq:2,who:'worker',label:'Worker · '+routeName(s.route),text:s.status==='Completed'?'The sample result and source evidence were saved with this step.':t.id==='captions'?'Speaker mapping is updated. The round-trip check is still running.':t.id==='search'?'The search shortcut opens the input. I am checking focus return to the reader after Escape.':t.id==='audio'?'The first verification reproduced a retry after cancellation. A focused repair is needed.':t.id==='import'?'18 duplicate matches found. No notes changed; the duplicate-note rule needs your decision.':'The cache key includes the requested size. I am adding bounded eviction.'},
    {id:'worker-tool',seq:3,who:'tool',tool:true,label:['captions','search'].includes(t.id)?'Bash · Process running':t.id==='audio'?'Test result · Exited 1':'Read · Completed',text:t.id==='audio'?'npm test -- export-retry-limits --run':t.id==='captions'?'python -m pytest tests/test_caption_roundtrip.py -q':t.id==='search'?'npm test -- search-keyboard.spec.ts --run':t.id==='import'?'src/import/mergeCustomerNotes.ts':state.scenario==='long-content'?'src/images/'+('deeply-nested-component/'.repeat(8))+'thumbnailCache.ts':'src/images/thumbnailCache.ts',result:t.id==='audio'?'FAIL: cancellation can schedule another retry. Trace: sample step 04 / verdict.md.':t.id==='captions'?'collected 8 items\nWaiting for the first test result. No output for 3m 12s; process is still running.':t.id==='search'?'RUN search-keyboard.spec.ts\nFocus-return check in progress.':t.id==='import'?'18 duplicate customers. No notes changed; awaiting the chosen merge rule.':'Read complete. Existing cache uses an unbounded Map; size-aware keys are required.'}];
  s.events=events;return events;
}
function contextSources(t){return [
  ['Original goal and acceptance criteria','Included','prompt.md and task acceptance entries','Goal: '+[...t.goal].slice(0,1200).join('')+'\n\nAcceptance:\n'+t.criteria.map(c=>c.id+': '+c.text+' — '+c.status).join('\n')],
  ['Saved decisions','Included','orchestrator/checkpoint.json · revision '+t.checkpoint,'Task decision: '+t.latest+'\nNext: review current evidence against the unmet criteria.\nCheckpoint revision '+t.checkpoint+' remains the last valid saved memory.'],
  ['Accepted first-step handoff','Partially included','step 01 / handoff.md · selected Findings and source references','Selected Findings: '+t.steps[0].name+' established the starting evidence for this task.\nGoal: '+[...t.goal].slice(0,1200).join('')+'\nOther sections remain in the original handoff and are not included in this excerpt.'],
  ['Selected task facts','Included','step 02 / facts.md',t.id==='thumbnails'?'Cache keys distinguish requested dimensions. Retention and regression evidence still need review. Source basis: sample revision 7.':t.latest+' Source basis: sample revision 7.'],
  ['Older troubleshooting','Available on demand','step 01 / notes.md','This older sample troubleshooting section was omitted from the decision packet for relevance. Opening it here does not mark it model-included. Original diagnostics remain in the saved task history.']
];}
function stepView(t){
  const s=t.steps[viewedStep-1],events=stepEvents(t,viewedStep),future=['Planned','Queued'].includes(s.status);
  return `<section class="panel" aria-label="Worker step chat"><header class="step-header"><h2>${String(viewedStep).padStart(2,'0')} · ${esc(s.name)}</h2><label class="sr" for="step-select">Choose step conversation</label><select id="step-select">${t.steps.map((step,i)=>`<option value="${i+1}" ${i+1===viewedStep?'selected':''}>${String(i+1).padStart(2,'0')} · ${esc(step.name)}</option>`).join('')}</select><div class="step-meta"><span>${future?'Worker route not assigned':esc(routeName(s.route))}</span><span data-step-state>${s.status}</span><span data-output-age>${s.status==='Running'?t.id==='captions'?'No output for 3m 12s · process running':'Latest output just now':'Saved sample history'}</span></div></header><div class="step-transcript" id="step-transcript" data-scroll="${t.id}-step-${viewedStep}" tabindex="0" aria-label="Chronological worker transcript"><div class="inner" data-stream="step">${future?`<div class="step-empty">This step has not started.<p class="muted small" style="margin-top:8px">Assignment: ${esc(s.name)}. ${esc(t.goal)}</p></div>`:events.map(e=>eventHTML(e)).join('')}</div></div><button class="btn new-activity" id="new-activity" hidden>New activity</button><footer class="readonly-footer">Worker transcript. Send task guidance to the orchestrator.<br><button class="btn link" data-message>Message orchestrator</button></footer></section>`;
}
function contextView(t){
  const renewed=t.id==='thumbnails'&&state.renewed;
  const sources=contextSources(t);
  return `<section class="context" data-scroll="${t.id}-context"><div class="inner"><h2>What this orchestrator receives</h2><p class="small muted" data-context-session style="margin-top:9px">${t.workerRunning?'Last decision context':'Current / last decision input'} · ${esc(t.session)}</p>${t.hold?'<div class="status-note attention">'+esc(t.hold)+'</div>':''}<section class="section"><h2>Current / last decision input</h2>${sources.map(([name,coverage,path],i)=>`<div class="source-row" data-source="${i}"><div class="row spread"><b>${name}</b><span class="badge">${coverage}</span></div><p>${esc(path)}</p><button class="btn link" data-artifact="source-${i}">Inspect source</button></div>`).join('')}</section><section class="section"><h2>Saved task memory</h2><p class="small">${esc(t.id==='thumbnails'?'Decisions: keep requested dimensions in the cache key; bound retained entries. Sources: accepted scout handoff and selected facts.':'Saved task decision: '+t.latest)}</p><p class="small muted" style="margin-top:8px">${esc(t.id==='thumbnails'?'Open risk: eviction and regression evidence are still needed. Next action: review the worker result against unmet criteria.':'Next action and open questions follow current task evidence and acceptance criteria.')} Task scope: ${t.number} only.</p><button class="btn link" data-artifact="checkpoint">Inspect checkpoint · revision ${t.checkpoint}</button></section><section class="section"><h2>Worker artifacts</h2><p class="small muted">Not automatically included in orchestrator context. Full transcripts are available in Step chat.</p>${t.steps.filter(s=>s.status==='Completed'||s.status==='Failed').map(s=>`<div class="source-row"><b>${esc(s.name)}</b><div class="row"><button class="btn link" data-artifact="handoff">Handoff</button><button class="btn link" data-artifact="facts">Facts</button>${s.kind==='Verify'?'<button class="btn link" data-artifact="verdict">Verdict</button>':''}</div></div>`).join('')}</section><details class="context-details" data-fold="${t.id}-context-bounds" ${expanded.has(t.id+'-context-bounds')?'open':''}><summary>Context details · prototype bounds</summary><dl><dt>Checkpoint</dt><dd>3.6 / 8 KiB</dd><dt>Initial packet</dt><dd data-packet>${renewed?'12.2':'18.4'} / 32 KiB</dd><dt>Artifact response limit</dt><dd>8 KiB / read</dd><dt>Additional results</dt><dd data-results>${renewed?'0':'6'} / 16 KiB</dd><dt>Tool calls</dt><dd data-calls>${renewed?'0':'3'} / 6</dd></dl><p>UTF-8 payload bytes, including envelopes. These are illustrative prototype bounds, not exact token guarantees.</p><p data-context-tokens style="margin-top:10px">${t.orchestratorContextTokens==null?'Last decision context: Unavailable':'Estimated last decision context: '+orchestratorContextLabel(t)+' tokens'}</p><p class="muted" style="margin-top:6px">Token estimate supplied separately from byte sizes. Archived worker history: retained unchanged, outside this packet. Viewing a source does not load it into a model or change usage.</p></details></div></section>`;
}
function taskView(){
  const t=currentTask();if(!t){view='tasks';return tasksView();}
  $('window').dataset.panel=panel;
  const active=panel==='orchestrator'?'overview':panel;
  return `<header class="task-head"><div class="row spread"><button class="btn" data-back>Back to Tasks</button>${badge(t)}</div><div class="project">${esc(t.project)} / ${t.number}</div><h1 tabindex="-1" id="task-title">${esc(t.title)}</h1></header><div class="task-layout"><aside class="orchestrator" aria-label="Task orchestrator conversation"><header class="orchestrator-head"><div class="row spread"><h2>Orchestrator</h2><span class="badge">${t.number}</span></div><p class="identity" data-owner>${esc(routeName(t.owner))} · ${t.effort}</p><p class="activity" data-activity>${esc(activityText(t))}</p></header><div class="thread" id="orchestrator-thread" data-scroll="${t.id}-orchestrator" tabindex="0" aria-label="Chronological task conversation"><div data-stream="orchestrator">${t.events.map(e=>eventHTML(e)).join('')}</div>${proposal(t)}</div>${composer(t)}</aside><div class="task-content"><nav class="tabs" role="tablist" aria-label="Task views">${[['orchestrator','Orchestrator'],['overview','Overview'],['step','Step chat'],['context','Context']].map(([id,name])=>`<button role="tab" id="tab-${id}" data-panel="${id}" class="${id==='orchestrator'?'mobile-tab':''}" aria-controls="task-panel" aria-selected="${panel===id||panel==='orchestrator'&&id==='overview'&&$('window').clientWidth>760}" tabindex="${panel===id||panel==='orchestrator'&&id==='overview'?0:-1}">${name}</button>`).join('')}</nav><div class="panel" id="task-panel" role="tabpanel" aria-labelledby="tab-${active}">${active==='overview'?overview(t):active==='step'?stepView(t):contextView(t)}</div></div></div>`;
}
function availabilityHTML(){return `<ul class="availability"><li>Codex · ${state.connections==='none'||state.connections==='codex-off'?'Disconnected':'Connected / enabled'} · Astra: ${routeExclusion('astra')||'orchestration and workers'}</li><li>Claude Code · ${state.connections==='none'?'Disconnected':'Connected / enabled'} · Opus: ${routeExclusion('opus')||'orchestration and verification'}; Sonnet: workers only</li><li>OpenCode · Disconnected · No eligible orchestration route</li><li>Command Code · Disabled · No eligible orchestration route</li></ul>`;}
function newView(){
  const d=state.newDraft;
  return `<div class="scroll" data-scroll="new"><div class="form-page"><header class="page-head"><h1>New task</h1><p>One task, with its own orchestrator.</p></header><form class="form" id="new-task-form"><div class="field"><label for="project">Project</label><select id="project">${['Catalog Atlas','Fieldnotes CRM','Waveform Studio','Frame Orchard','Harbor Reader','Ledger Grove'].map(p=>`<option ${p===d.project?'selected':''}>${p}</option>`).join('')}</select></div><div class="field"><label for="goal">Task goal</label><textarea id="goal" required maxlength="4000">${esc(d.goal)}</textarea></div><div class="field"><label for="acceptance">Acceptance criteria <span class="muted">(optional)</span></label><textarea id="acceptance" maxlength="4000">${esc(d.criteria)}</textarea><p>One criterion per line. Omitted criteria remain to be defined and are not passed.</p></div><div class="field"><label for="owner-route">Orchestrator</label><select id="owner-route"><option value="auto">Auto</option>${['astra','opus'].filter(k=>!routeExclusion(k)||d.route===k).map(k=>`<option value="${k}" ${d.route===k?'selected':''} ${routeExclusion(k)?'disabled':''}>${esc(routeName(k))}${routeExclusion(k)?' (unavailable)':''}</option>`).join('')}</select><p>Assigned once when the task starts. Uses the global model usage balance.</p><p>Inherited effort: ${state.effort}. Existing tasks keep their saved effort.</p></div><div class="preview" id="assignment-preview"></div><details><summary>Sample route availability</summary>${availabilityHTML()}</details><p class="form-error" id="start-error" role="status"></p><div class="row"><button class="btn ink" type="submit" id="start-task">Start task</button><button class="btn" type="button" data-view="tasks">Cancel</button></div></form></div></div>`;
}
function updatePreview(){
  if(view!=='new')return;
  $('owner-route').querySelectorAll('option').forEach(option=>{if(option.value!=='auto')option.disabled=!!routeExclusion(option.value);});
  const key=state.newDraft.route==='auto'?assignment():state.newDraft.route,why=key?routeExclusion(key):'No connected, enabled CLI with proven orchestration tools is available.';
  $('assignment-preview').innerHTML=key&&!why?`<b>Provisional preview: ${esc(routeName(key))}</b><p>Resolved effort: ${resolvedEffort(key,state.effort)}. Availability and shared activity are rechecked at Start.</p>`:`<b>No eligible orchestrator</b><p>${esc(why)}</p>`;
  $('start-task').disabled=!!why;$('start-task').title=why||'Create a local sample task';
  if(state.newDraft.route!=='auto'&&why){$('start-error').textContent='The explicit '+routeName(key)+' pick is unavailable: '+why+' Choose an eligible route; it will not be substituted.';$('start-task').disabled=false;}
}
function settingsView(){return `<div class="scroll" data-scroll="settings"><div class="form-page"><header class="page-head"><h1>Orchestrator settings</h1><p>Defaults for newly assigned tasks.</p></header><form class="form" id="settings-form"><div class="field"><label for="effort">Default orchestrator effort</label><select id="effort">${['low','medium','high','xhigh','max'].map(e=>`<option value="${e}" ${state.effort===e?'selected':''}>${e[0].toUpperCase()+e.slice(1)}</option>`).join('')}</select><p>Sample Codex mapping: Low → Low, Medium → Medium, High / Xhigh / Max → High. Sample Claude mapping passes each label through.</p><p>These fixture mappings do not prove installed provider support. Worker effort remains independent.</p></div><div><button class="btn ink" type="submit">Save default</button></div><p class="small good" id="settings-feedback" role="status"></p></form><section class="section"><h2>Sample connections and capability</h2>${availabilityHTML()}<p class="hint">Read-only sample. Installed worker support alone does not establish restricted orchestration capability.</p></section></div></div>`;}
function usageView(){
  const sum=total();const roleLabels={orchestrator:'Orchestration',worker:'Workers',other:'Other sessions'};
  return `<div class="scroll" data-scroll="usage"><div class="inner"><header class="page-head"><h1>Global usage</h1><p>Fictional processed-token totals and sample cost estimates.</p></header><p class="small muted">Orchestration is included in each model total. Role and task breakdowns are subsets of the same records.</p><div class="usage-total" data-global-tokens="${sum.tokens}" data-global-cents="${sum.cents}">${number(sum.tokens)} processed tokens / ${money(sum.cents)}${sum.unknown?' known subtotal':''}</div>${sum.unknown?`<p class="attention" data-unknown>${sum.unknown} session with unavailable usage. Unknown is not zero.</p>`:''}<div class="table-wrap"><table class="usage-table"><thead><tr><th scope="col">Model / role breakdown</th><th scope="col">Processed tokens</th><th scope="col">Sample estimate</th></tr></thead><tbody>${['Astra','Opus','Sonnet'].map(model=>{const rows=state.ledger.filter(r=>r.model===model),s=total(rows);return `<tr data-model="${model}" data-tokens="${s.tokens}" data-cents="${s.cents}"><td><b>${model}</b><p class="hint">${model==='Astra'?'Codex':'Claude Code'}</p><details><summary>Role breakdown</summary><div class="role-breakdown">${Object.entries(roleLabels).map(([role,label])=>{const r=total(rows.filter(row=>row.role===role));return `<p data-role="${role}">${label}: ${number(r.tokens)} / ${money(r.cents)}${r.unknown?' known; usage unavailable for '+r.unknown+' session':''}</p>`;}).join('')}</div></details></td><td class="numbers">${number(s.tokens)}${s.unknown?'<br>+ unavailable':''}</td><td class="numbers">${money(s.cents)}${s.unknown?'<br>+ unavailable':''}</td></tr>`;}).join('')}</tbody></table></div><section class="section"><h2>Task attribution</h2>${state.tasks.map(t=>`<div class="source-row"><b>${t.number} · ${esc(t.project)}</b>${usageSubset(t)}</div>`).join('')}</section><p class="bottom-note">Other sessions: ${number(total(state.ledger.filter(r=>r.role==='other')).tokens)} / ${money(total(state.ledger.filter(r=>r.role==='other')).cents)}. No additional allowance or quota is implied. Costs are authored sample estimates, not current vendor prices.</p></div></div>`;
}
function observedView(){return `<div class="scroll" data-scroll="observed"><div class="inner"><header class="page-head"><div class="project">Paper Kite Docs / VS Code</div><h1>Observed session</h1><p>Compare offline search libraries</p></header><div class="status-note"><h2>Read-only in Console</h2><p>Reply in the original VS Code chat. This external session has no assigned orchestrator.</p></div><section class="section"><div class="event user"><div class="speaker">You · external session</div><p>Compare local search options for an offline documentation bundle.</p></div><div class="event"><div class="speaker">Opus · external VS Code session</div><p>Should the bundle index PDFs as well as HTML pages?</p></div></section><p class="small muted" data-observed-usage>Known sample usage: ${number(total(state.ledger.filter(r=>r.id==='u14')).tokens)} processed tokens / ${money(total(state.ledger.filter(r=>r.id==='u14')).cents)}. Included once in Opus / Other sessions (record u14).</p><button class="btn" data-view="tasks" style="margin-top:20px">Back to Tasks</button></div></div>`;}
function render(){
  $('top-count').textContent=state.tasks.filter(isAttention).length+' for you';
  $('usage-strip').innerHTML=usageStrip();
  document.querySelectorAll('.topbar [data-view]').forEach(b=>b.setAttribute('aria-current',b.dataset.view===view||view==='task'&&b.dataset.view==='tasks'?'page':'false'));
  $('main').innerHTML=view==='task'?taskView():view==='new'?newView():view==='settings'?settingsView():view==='usage'?usageView():view==='observed'?observedView():tasksView();
  restorePositions();updatePreview();
  document.querySelectorAll('[data-preview-task]').forEach(el=>{if(state.following[el.dataset.previewTask]!==false)el.scrollTop=el.scrollHeight;});
}
function navigate(next,options={}) {
  savePositions();view=next;
  if(next==='task') {selected=options.task||selected;const t=currentTask();viewedStep=options.step||t?.current||1;const narrow=$('window').clientWidth<=760;panel=options.panel||(narrow?'orchestrator':'overview');}
  render();
  if(options.focusMessage)focusComposer();
  else if(next==='task')$('task-title')?.focus({preventScroll:true});
  else if(next==='tasks'&&homeFocus)document.querySelector('[data-focus="'+homeFocus+'"]')?.focus({preventScroll:true});
}
function changePanel(next,focus=false){savePositions();panel=next;render();if(focus)$('tab-'+next)?.focus({preventScroll:true});}
function focusComposer(){
  if($('window').clientWidth<=760&&panel!=='orchestrator'){savePositions();panel='orchestrator';render();}
  if(currentTask()?.status==='accepted')document.querySelector('.composer-closed button')?.focus();else $('task-draft')?.focus({preventScroll:true});
}
function inspect(title,body){dialogReturn=document.activeElement;$('dialog-title').textContent=title;$('dialog-body').innerHTML=body;$('inspector').showModal();$('close-dialog').focus();}
function artifact(id){
  const t=currentTask();let content;
  if(id.startsWith('source-')){
    const source=contextSources(t)[Number(id.slice(7))];if(!source)return;
    inspect(t.number+' / '+source[0],'<p class="mono">'+esc(source[2])+'</p><p class="muted small">Bounded fictional excerpt. Full source retained. Inspection does not change model inclusion or usage.</p><pre>'+esc(source[3])+'</pre>');return;
  }
  if(id==='checkpoint')content=`Task: ${t.number}\nCheckpoint revision: ${t.checkpoint} (last valid)\nProgress: selected evidence reviewed.\nDecision: ${t.id==='thumbnails'?'preserve requested dimensions and bound retention':t.latest}\nSource: step 01 / handoff.md; selected task facts\nOpen: unmet acceptance criteria\nNext: review the worker result against unmet criteria.\nOmitted references remain available in saved task history.`;
  else if(id.startsWith('AC')){const c=t.criteria.find(c=>c.id===id);content=`${c.id}: ${c.text}\nState: ${c.status}\nSource: ${t.number} / step ${t.current} / verdict.md\nChecked basis: ${c.basis}\n${c.status==='Needs recheck'?'Previous pass retained. A later writing change requires a new check.':c.status==='Failed'?'FAIL: cancellation can schedule a retry. A focused repair and fresh verification are required.':'Sample current check passed; user acceptance remains separate.'}`;}
  else if(id==='handoff')content='Goal\n'+t.goal+'\n\nFindings\nSelected observations and source evidence, not a full worker transcript.\n\nFiles touched\nSample project source only.\n\nTroubleshooting\nOriginal diagnostics retained in the step files.\n\nOpen questions\nSee current task criteria.\n\nNext\nCheck the unmet acceptance criteria before choosing further work.';
  else if(id==='facts')content=t.id==='thumbnails'?'Code-read sample facts: cache keys distinguish dimensions. Retention verification is not yet complete. Source revision: 7.':'Selected task facts for '+t.number+': '+t.latest+' Source: saved step evidence, sample revision 7.';
  else if(id==='verdict')content='Sample verification result. Evidence must match the current result revision. An ended process alone does not establish acceptance.';
  else content='Bounded source inspection for '+t.number+'.\nCoverage: selected section only; the original artifact remains intact.\nSource: '+id+' / sample revision 7\nThis inspection does not add the source to orchestrator input.';
  inspect(t.number+' / '+(id==='checkpoint'?'orchestrator/checkpoint.json':id),'<p class="muted small">Bounded fictional artifact. Inspection does not alter context inclusion or usage.</p><pre>'+esc(content)+'</pre>');
}
function act(action){
  const t=currentTask();if(!t)return;
  if(action==='stop'){inspect('Stop '+t.number+'?',`<p>${t.workerRunning?'Stop the current step '+String(t.current).padStart(2,'0')+' worker and prevent new progression.':'End current task activity and prevent new progression.'} History and unresolved guidance stay saved.</p><div class="row" style="margin-top:18px"><button class="btn" data-confirm-stop>Stop task</button><button class="btn" data-cancel-dialog>Keep task</button></div>`);return;}
  if(action==='approve'&&t.status==='proposal'){
    t.steps.push({name:'Repair cancellation race',kind:'Code',route:'sonnet',status:'Running'},{name:'Reverify cancellation and retry limits',kind:'Verify',route:'opus',status:'Planned'});t.current=t.steps.length-1;t.status='running';t.workerRunning=true;t.latest='Approved focused repair at step 05. Verification at step 06 is planned and has not started.';event(t,'user','Approved the focused repair proposal.');event(t,'receipt','Assigned step 05 to Sonnet / Claude Code. Step 06 verification remains planned.');
  }else if(action==='reject'&&t.status==='proposal'){t.status='held';t.hold='Proposal rejected. No repair was started. Add a note to the orchestrator before a new proposal.';event(t,'user','Rejected the repair proposal.');}
  else if(action==='accept'&&t.status==='ready'&&t.criteria.every(c=>c.status==='Passed')){t.status='accepted';event(t,'user','Accepted the sample result.');notify('Result accepted in this sample.');}
  else if(action==='reopen'&&t.status==='accepted'){t.status='held';t.hold='Reopened explicitly. Send the next task guidance; the same orchestrator is retained.';event(t,'user','Reopened the task.');}
  else if(action==='pause'&&!['accepted','stopped','paused'].includes(t.status)){t.beforePause=t.status;t.status='paused';t.latest=t.workerRunning?'Progression paused. The existing worker is still running; no new step can start.':'Progression paused. Queued guidance is retained.';event(t,'receipt',t.latest);}
  else if(action==='resume'&&t.status==='paused'){const why=routeExclusion(t.owner)||t.hold;if(why){notify('Resume unavailable: '+why);return;}t.status=t.beforePause||'running';event(t,'receipt','Resumed through current gates. Saved guidance remains queued until its receipt event.');}
  else if(action==='recover'&&t.status==='stopped'){inspect('Recovery for '+t.number,'<p>The current worker ended. No automatic retry is scheduled.</p><p class="muted small" style="margin-top:10px">A production recovery must reconcile the stopped run and unresolved guidance first. This mockup retains history and does not fabricate that recovery.</p>');return;}
  else return;
  savePositions();render();
}
function send(){
  const t=currentTask();if(!t||t.status==='accepted'||!t.draft.trim())return;
  const question=t.question&&!t.answerQueued?t.question:null;
  const e=event(t,'user',t.draft.trim(),{label:question?'You · answer to step '+String(question.step).padStart(2,'0'):'You · task guidance',recipient:t.number+'-orchestrator',question:question?.id,delivery:'Queued'});
  state.pending.push({task:t.id,event:e.id,phase:0,question:question?.id,step:question?.step||t.current});
  if(question)t.answerQueued=true;t.draft='';savePositions();render();focusComposer();notify('Saved for '+t.number+' orchestrator. Queued; receipt is a separate event.');
}
function updateStream(container,events){
  if(!container)return;
  const scroller=container.closest('.thread,.step-transcript,.tile-stream'),follow=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<32;
  for(const e of events){let node=container.querySelector(':scope > [data-event="'+e.id+'"]');if(!node){container.insertAdjacentHTML('beforeend',eventHTML(e,scroller.dataset.previewTask?scroller.dataset.previewTask+'-preview':selected));continue;}const field=node.querySelector('[data-field=text]');if(field&&field.textContent!==e.text)field.textContent=e.text;const result=node.querySelector('.tool-body pre');if(result&&result.textContent!==e.result)result.textContent=e.result;}
  if(follow)scroller.scrollTop=scroller.scrollHeight;else if(container.dataset.stream==='step'&&$('new-activity'))$('new-activity').hidden=false;
}
function advance(){
  const previousTaskStates=state.tasks.map(t=>[t.id,t.status,t.current,t.workerRunning].join(':')).join('|');
  state.tick++;
  const t31=state.tasks.find(t=>t.id==='thumbnails');
  if(state.scenario==='renewal'&&!state.renewed){state.renewed=true;t31.session='thumbnails-decision-08';t31.orchestratorContextTokens=4100;event(t31,'receipt','New session, same orchestrator. Astra / Codex, high effort. Checkpoint revision 7 loaded; archived history retained.');addUsage({id:'u-renewal-031',task:'T-031',role:'orchestrator',model:'Astra',tokens:3000,cents:3});}
  for(const p of state.pending){
    const t=state.tasks.find(t=>t.id===p.task);if(!t||routeExclusion(t.owner)||['paused','stopped','accepted','held','capacity'].includes(t.status)||p.phase>=2)continue;
    if(state.scenario==='delivery-uncertain'){if(p.phase===0){event(t,'receipt','Delivery unconfirmed. Saved message retained; no automatic resend.',{label:'Uncertain delivery',recipient:t.number+'-orchestrator'});p.phase=2;}continue;}
    if(p.phase===0){event(t,'receipt','Received by orchestrator',{label:'Receipt · saved message '+p.event,question:p.question,recipient:t.number+'-orchestrator'});p.phase=1;}
    else {event(t,'receipt','Delivered to step '+String(p.step).padStart(2,'0'),{label:'Worker delivery · source step '+String(p.step).padStart(2,'0'),question:p.question});p.phase=2;if(p.question){t.question=null;t.status='running';t.workerRunning=true;t.steps[p.step-1].status='Running';t.latest='The chosen duplicate-note rule was delivered to step 03.';}}
  }
  if(state.scenario==='capacity'&&state.tick===2){t31.status='running';t31.workerRunning=true;t31.steps[2].status='Running';t31.latest='Capacity became available. The queued worker is now running.';event(t31,'receipt','Worker capacity available. Step 03 started once.');}
  for(const t of state.tasks.filter(t=>t.workerRunning)){
    const s=t.steps[t.current-1],events=stepEvents(t,t.current);
    if(t.id==='thumbnails'){
      const messages={1:'The cache key includes the requested size. I am adding bounded eviction.',2:'The edit is saved. I will check dimensions and eviction before handoff.',4:'The worker checks are running. No acceptance decision has been made.',6:'The size-aware check passed. Retention and regression coverage still need verification.'};
      if(messages[state.tick])events.push({id:'stream-'+state.tick,seq:events.length+1,who:'worker',label:'Worker · step 03',text:messages[state.tick]});
      if(state.tick===2){events.push({id:'stream-test',seq:events.length+1,who:'tool',tool:true,label:'Test · sample output',text:'npm test -- thumbnailCache --run',result:'RUN thumbnailCache.spec.ts\nSize-aware key: PASS\nEviction check: running'});if(t.criteria[0].status==='Passed')t.criteria[0].status='Needs recheck';}
      const output=events.find(e=>e.id==='stream-test');if(output&&state.tick>=4)output.result='Size-aware key: PASS\nEviction check: PASS\nWorker output awaits current acceptance review.';
    }
    if(t.id==='audio'&&s.name==='Repair cancellation race'&&state.tick===3){s.status='Completed';t.workerRunning=false;t.status='deciding';t.latest='Repair handoff received. The next verification is still planned until its launch event.';t.criteria.forEach(c=>{if(c.status==='Passed')c.status='Needs recheck';});event(t,'receipt','Step 05 repair result received. Current verification evidence must be refreshed.');}
  }
  const audio=state.tasks.find(t=>t.id==='audio');
  if(audio?.status==='deciding'&&state.tick===4){audio.current=audio.steps.length;audio.steps[audio.current-1].status='Running';audio.status='running';audio.workerRunning=true;event(audio,'receipt','Step 06 verification started after the repair handoff was reviewed.');}
  if(view==='task'){
    const t=currentTask();updateStream(document.querySelector('[data-stream=orchestrator]'),t.events);
    if(panel==='step')updateStream(document.querySelector('[data-stream=step]'),stepEvents(t,viewedStep));
    document.querySelector('[data-activity]').textContent=activityText(t);
    const statusBadge=document.querySelector('.task-head .badge');
    statusBadge.lastChild.textContent=stateLabels[t.status];statusBadge.classList.toggle('attention',isAttention(t));
    const stepState=document.querySelector('[data-step-state]');if(stepState)stepState.textContent=t.steps[viewedStep-1].status;
    if(panel==='context'&&state.scenario==='renewal'){
      document.querySelector('[data-context-session]').textContent='Current / last decision input · '+t.session;
      const packet=document.querySelector('[data-packet]');if(packet)packet.textContent='12.2 / 32 KiB';
      const results=document.querySelector('[data-results]');if(results)results.textContent='0 / 16 KiB';
      const calls=document.querySelector('[data-calls]');if(calls)calls.textContent='0 / 6';
      const tokens=document.querySelector('[data-context-tokens]');if(tokens)tokens.textContent=t.orchestratorContextTokens==null?'Last decision context: Unavailable':'Estimated last decision context: '+orchestratorContextLabel(t)+' tokens';
    }
    if(panel==='overview'){
      const note=document.querySelector('.overview .status-note');note.querySelector('h3').textContent=stateLabels[t.status];note.querySelector('p').textContent=t.hold||t.latest;
      for(const c of t.criteria){const row=document.querySelector('[data-criterion="'+c.id+'"]');if(row.querySelector('.state').textContent!==c.status){row.querySelector('.state').textContent=c.status;row.querySelector('.state').classList.remove('good');row.querySelector('small').textContent='A later writing change invalidated the current basis; the previous pass remains in history.';}}
      t.steps.forEach((s,i)=>{const row=document.querySelector('[data-step="'+(i+1)+'"]');if(row){row.classList.toggle('current',i+1===t.current);row.querySelector('p').textContent=s.kind+' · '+s.status+(s.status!=='Planned'?' · '+routeName(s.route):'');row.querySelector('button').textContent=s.status==='Planned'?'View planned step':s.status==='Completed'||s.status==='Failed'?'View result':'Open step chat';}});
      const rows=state.ledger.filter(r=>r.task===t.number),sum=total(rows),o=total(rows.filter(r=>r.role==='orchestrator')),w=total(rows.filter(r=>r.role==='worker')),subset=document.querySelector('[data-task-tokens]');
      subset.dataset.taskTokens=sum.tokens;subset.dataset.taskCents=sum.cents;subset.textContent=number(sum.tokens)+' processed tokens / '+money(sum.cents)+' sample estimate'+(sum.unknown?' known subtotal; '+sum.unknown+' session with unavailable usage':'');
      subset.nextElementSibling.textContent='Orchestration '+number(o.tokens)+' / '+money(o.cents)+' · Workers '+number(w.tokens)+' / '+money(w.cents)+'. Included in global usage.';
    }
  }else if(view==='tasks'){
    const structuralChange=previousTaskStates!==state.tasks.map(t=>[t.id,t.status,t.current,t.workerRunning].join(':')).join('|');
    if(structuralChange){savePositions();render();}
    document.querySelectorAll('[data-preview-task]').forEach(el=>{
      const t=state.tasks.find(t=>t.id===el.dataset.previewTask);if(!t)return;
      updateStream(el.firstElementChild,stepEvents(t,t.current));
      const follow=el.scrollHeight-el.scrollTop-el.clientHeight<32;state.following[t.id]=follow;
      const button=document.querySelector('[data-follow="'+t.id+'"]');button.hidden=follow;button.setAttribute('aria-pressed',String(follow));
    });
  }else if(view==='usage'){savePositions();render();}
  if(state.scenario==='renewal')$('usage-strip').innerHTML=usageStrip();
  document.querySelectorAll('[data-task-telemetry]').forEach(el=>{const t=state.tasks.find(t=>t.id===el.dataset.taskTelemetry),html=taskTelemetry(t);if(el.innerHTML!==html)el.innerHTML=html;});
  $('top-count').textContent=state.tasks.filter(isAttention).length+' for you';
  if(state.tick>=12&&playing)setPlaying(false);
}
function setPlaying(value){playing=value;clearInterval(timer);if(playing)timer=setInterval(advance,1000);$('playback').textContent=playing?'Pause stream':'Play stream';$('playback').setAttribute('aria-pressed',String(playing));document.querySelectorAll('[data-grid-play]').forEach(b=>{b.textContent=playing?'Pause streams':'Play streams';b.setAttribute('aria-pressed',String(playing));});document.documentElement.dataset.playback=playing?'playing':'paused';}
function setScenario(id){
  setPlaying(false);baseState();positions={};expanded.clear();selected=null;view='tasks';panel='overview';state.scenario=id;const t=state.tasks.find(t=>t.id==='thumbnails');
  expanded.add('captions-preview-worker-tool');expanded.add('search-preview-worker-tool');
  if(holdReasons[id]){t.status='held';t.hold=holdReasons[id];t.workerRunning=false;t.steps[2].status=id==='uncertain'?'Outcome unknown':'Completed';}
  if(id==='cli-unavailable')state.connections='codex-off';
  if(id==='paused'){t.beforePause='running';t.status='paused';t.latest='Progression paused. The existing step 03 worker is still running; no new step can start.';event(t,'user','Keep the image dimensions unchanged.',{delivery:'Queued',recipient:'T-031-orchestrator'});state.pending.push({task:t.id,event:'paused-guidance',phase:0,step:3});}
  if(id==='stopped'){t.status='stopped';t.workerRunning=false;t.steps[2].status='Stopped';t.latest='You stopped step 03. Its history is retained and no automatic retry is scheduled.';}
  if(id==='capacity'){t.status='capacity';t.workerRunning=false;t.steps[2].status='Queued';t.steps[2].contextTokens=null;t.latest='Step 03 is prepared but shared worker capacity is unavailable. No worker has started.';}
  if(id==='renewal'){t.workerRunning=false;t.status='deciding';t.steps[2].status='Completed';t.latest='Renewal is prepared at a safe boundary. Step simulation admits the new decision session once.';event(t,'receipt','Context renewal prepared. New session will retain the same orchestrator and effort.');}
  if(id==='accepted'){const a=state.tasks.find(t=>t.id==='archive');a.status='accepted';event(a,'user','Accepted the sample result explicitly.');}
  if(id==='stale-verification'){const a=state.tasks.find(t=>t.id==='archive');a.status='held';a.hold='A later writing change invalidated the prior verification. Current acceptance is unavailable until rechecked.';a.criteria.forEach(c=>c.status='Needs recheck');}
  if(id==='unknown-usage'){t.orchestratorContextTokens=null;addUsage({id:'u-unknown',task:'T-031',role:'orchestrator',model:'Astra',tokens:null,cents:null});}
  if(id==='delivery-uncertain'){const e=event(t,'user','Keep the image dimensions unchanged.',{recipient:'T-031-orchestrator',delivery:'Queued'});event(t,'receipt','Delivery unconfirmed. Saved message retained; no automatic resend.',{label:'Uncertain delivery',recipient:'T-031-orchestrator'});state.pending.push({task:t.id,event:e.id,phase:2,step:3});t.latest='A saved guidance message has unconfirmed delivery. No automatic resend is permitted.';}
  if(id==='no-eligible-cli')state.connections='none';
  if(id==='empty')state.tasks=[];
  if(id==='long-content'){t.title='Cache product thumbnails while preserving requested dimensions across nested catalog variants and exceptionally long product names';routeInfo.astra.display='Astra sample model with an exceptionally long descriptive display label';}
  else delete routeInfo.astra.display;
  if(!['default','empty','loading','offline','no-eligible-cli','unknown-usage'].includes(id)){view='task';selected=['question'].includes(id)?'import':id==='proposal'?'audio':['ready','accepted','stale-verification'].includes(id)?'archive':'thumbnails';viewedStep=currentTask().current;panel=$('window').clientWidth<=760?'orchestrator':'overview';}
  if(id==='no-eligible-cli')view='new';if(id==='unknown-usage')view='usage';
  $('scenario').value=id;$('connections').value=state.connections;$('activity').value=state.activity;$('feedback').hidden=true;render();
}
document.addEventListener('click',e=>{
  document.querySelectorAll('.tile-details[open]').forEach(d=>{if(!d.contains(e.target))d.open=false;});
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.projectScope){savePositions();state.projectScope=b.dataset.projectScope;positions.tasks=0;render();[...document.querySelectorAll('[data-project-scope]')].find(el=>el.dataset.projectScope===state.projectScope)?.focus({preventScroll:true});return;}
  if(b.hasAttribute('data-grid-filter')){savePositions();state.gridFilter=b.dataset.gridFilter;positions.tasks=0;render();document.querySelector('[data-grid-filter="'+state.gridFilter+'"]')?.focus({preventScroll:true});return;}
  if(b.hasAttribute('data-decisions')){state.projectScope='all';state.gridFilter='needs';navigate('tasks');return;}
  if(b.hasAttribute('data-grid-play')){setPlaying(!playing);return;}
  if(b.dataset.follow){const stream=document.querySelector('[data-preview-task="'+b.dataset.follow+'"]');state.following[b.dataset.follow]=true;stream.scrollTop=stream.scrollHeight;b.hidden=true;b.setAttribute('aria-pressed','true');return;}
  if(b.dataset.view){navigate(b.dataset.view);return;}
  if(b.dataset.open){homeFocus=b.dataset.focus||'title-'+b.dataset.open;navigate('task',{task:b.dataset.open,panel:b.dataset.openPanel||(b.dataset.reply?'orchestrator':undefined),focusMessage:!!b.dataset.reply});return;}
  if(b.hasAttribute('data-back')){navigate('tasks');return;}
  if(b.dataset.panel){changePanel(b.dataset.panel,true);return;}
  if(b.dataset.stepOpen){viewedStep=Number(b.dataset.stepOpen);changePanel('step');return;}
  if(b.hasAttribute('data-message')){focusComposer();return;}
  if(b.dataset.suggest){currentTask().draft=b.dataset.suggest;$('task-draft').value=b.dataset.suggest;$('task-draft').focus();return;}
  if(b.dataset.artifact){artifact(b.dataset.artifact);return;}
  if(b.dataset.action){act(b.dataset.action);return;}
  if(b.hasAttribute('data-confirm-stop')){const t=currentTask();t.status='stopped';t.workerRunning=false;t.steps[t.current-1].status='Stopped';t.latest='You stopped the current execution. History and unresolved guidance are retained; no automatic retry.';event(t,'user','Stopped current task execution. Queued guidance retained.');$('inspector').close();render();notify('Current execution stopped. Saved guidance retained.');return;}
  if(b.hasAttribute('data-cancel-dialog')){$('inspector').close();return;}
  if(b.hasAttribute('data-snapshot')){setScenario('default');return;}
});
document.addEventListener('input',e=>{if(e.target.id==='task-draft')currentTask().draft=e.target.value;const fields={goal:'goal',acceptance:'criteria',project:'project','owner-route':'route'};if(fields[e.target.id]){state.newDraft[fields[e.target.id]]=e.target.value;updatePreview();}});
document.addEventListener('submit',e=>{
  e.preventDefault();if(e.target.id==='task-form'){send();return;}
  if(e.target.id==='settings-form'){state.effort=$('effort').value;$('settings-feedback').textContent='Applies to newly assigned tasks. Existing tasks keep their effort.';return;}
  if(e.target.id==='new-task-form'){
    const d=state.newDraft,key=d.route==='auto'?assignment():d.route,why=key?routeExclusion(key):'No eligible CLI is connected.';
    if(!key||why){$('start-error').textContent='Start refused: '+why+' The explicit pick and draft are retained. No substitution.';return;}
    if(!d.goal.trim())return;
    const n=state.tasks.length+41,id='new-'+n,criteria=d.criteria.split('\n').map(s=>s.trim()).filter(Boolean);
    const t={id,number:'T-'+String(n).padStart(3,'0'),title:d.goal.trim(),goal:d.goal.trim(),project:d.project,owner:key,effort:resolvedEffort(key,state.effort),status:'deciding',current:1,mode:'Gated',latest:'Assignment saved. Local sample decision prepared; no real CLI was started.',draft:'',sequence:0,events:[],session:id+'-decision-01',checkpoint:1,hold:'',workerRunning:false,criteria:(criteria.length?criteria:['Acceptance criteria to be defined.']).map((text,i)=>({id:'AC'+(i+1),text,status:'Not checked',basis:null})),steps:[{name:'Choose next step from unmet criteria',kind:'Explain',route:key,status:'Planned'}]};
    state.tasks.push(t);event(t,'user',t.goal,{label:'You · original goal'});event(t,'receipt','Assigned '+routeName(key)+' with '+t.effort+' effort. Assignment is fixed for this task.');
    const preview=$('assignment-preview').innerText;notify('Task created locally. Actual assignment: '+routeName(key)+'.'+(preview.includes(routeName(key))?'':' The provisional preview changed at Start.'));
    state.newDraft={project:d.project,goal:'',criteria:'',route:'auto'};navigate('task',{task:id});
  }
});
document.addEventListener('change',e=>{
  if(e.target.id==='project-scope'){savePositions();state.projectScope=e.target.value;positions.tasks=0;render();$('project-scope').focus({preventScroll:true});}
  if(e.target.id==='step-select'){savePositions();viewedStep=Number(e.target.value);render();$('step-select').focus({preventScroll:true});}
  if(e.target.id==='scenario')setScenario(e.target.value);
  if(e.target.id==='viewport')$('window').style.maxWidth=e.target.value+'px';
  if(e.target.id==='connections'){
    state.connections=e.target.value;
    const waiting=state.tasks.find(t=>t.id==='thumbnails');
    if(state.scenario==='cli-unavailable'&&waiting.status==='held'&&!routeExclusion(waiting.owner)){waiting.status='deciding';waiting.hold='';waiting.latest='Codex reconnected. The saved Astra owner can resume at the next safe decision boundary.';event(waiting,'receipt',waiting.latest);}
    updatePreview();if(['task','settings'].includes(view)){savePositions();render();}notify('Sample connection snapshot changed. Existing task assignments are retained.');
  }
  if(e.target.id==='activity'){state.activity=e.target.value;updatePreview();}
  if(e.target.id==='project'||e.target.id==='owner-route'){state.newDraft[e.target.id==='project'?'project':'route']=e.target.value;updatePreview();}
});
document.addEventListener('toggle',e=>{if(e.target.dataset.fold){if(e.target.open)expanded.add(e.target.dataset.fold);else expanded.delete(e.target.dataset.fold);}},true);
document.addEventListener('scroll',e=>{const el=e.target;if(!el.dataset?.previewTask)return;const id=el.dataset.previewTask,follow=el.scrollHeight-el.scrollTop-el.clientHeight<32;state.following[id]=follow;positions['preview-'+id]=el.scrollTop;const b=document.querySelector('[data-follow="'+id+'"]');if(b){b.hidden=follow;b.setAttribute('aria-pressed',String(follow));}},true);
document.addEventListener('keydown',e=>{
  const metadata=document.querySelector('.tile-details[open]');
  if(e.key==='Escape'&&metadata){e.preventDefault();metadata.open=false;metadata.querySelector('summary').focus({preventScroll:true});return;}
  if($('inspector').open&&e.key==='Tab'){
    const controls=[...$('inspector').querySelectorAll('button,a,input,textarea,select,[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);
    const end=e.shiftKey?controls[0]:controls.at(-1);
    if(document.activeElement===end){e.preventDefault();(e.shiftKey?controls.at(-1):controls[0]).focus();}
  }
  if(e.target.id==='task-draft'&&e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();send();}
  if(e.target.getAttribute('role')==='tab'&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){
    e.preventDefault();const tabs=[...document.querySelectorAll('[role=tab]')].filter(b=>b.getClientRects().length);let i=tabs.indexOf(e.target);i=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;changePanel(tabs[i].dataset.panel,true);
  }
});
$('theme').onclick=()=>{const light=document.documentElement.dataset.theme!=='light';document.documentElement.dataset.theme=light?'light':'dark';$('theme').textContent=light?'Dark theme':'Light theme';};
$('playback').onclick=()=>setPlaying(!playing);$('advance').onclick=advance;$('reset').onclick=()=>{if($('inspector').open)$('inspector').close();setScenario('default');};
$('close-dialog').onclick=()=>$('inspector').close();$('inspector').addEventListener('close',()=>{if(dialogReturn?.isConnected)dialogReturn.focus({preventScroll:true});});
document.addEventListener('click',e=>{if(e.target.id==='new-activity'){$('step-transcript').scrollTop=$('step-transcript').scrollHeight;e.target.hidden=true;}});
$('scenario').innerHTML=Object.entries(scenarioNames).map(([id,name],i)=>`<option value="${id}">S${String(i+1).padStart(2,'0')} · ${name}</option>`).join('');
const params=new URLSearchParams(location.search);const requestedScenario=params.get('scenario');setScenario(scenarioNames[requestedScenario]?requestedScenario:'default');
if(params.get('theme')==='light')$('theme').click();
if(['340','400','900','1460'].includes(params.get('width'))){$('window').style.maxWidth=params.get('width')+'px';$('viewport').value=params.get('width');}
const requestedView=params.get('view');
if(['tasks','new','settings','usage','observed'].includes(requestedView)){view=requestedView;render();}
else if(requestedView==='task'&&state.tasks.some(t=>t.id===params.get('task'))){selected=params.get('task');view='task';panel=['orchestrator','overview','step','context'].includes(params.get('panel'))?params.get('panel'):$('window').clientWidth<=760?'orchestrator':'overview';const n=Number(params.get('step'));viewedStep=Number.isInteger(n)&&n>=1&&n<=currentTask().steps.length?n:currentTask().current;render();}
else if(requestedView){view='tasks';selected=null;render();}
if(params.get('stream')==='playing')setPlaying(true);
// shortcut: fixtures and drafts live in one tab; integrate served actions and persisted receipts only after a separately approved runtime build.
