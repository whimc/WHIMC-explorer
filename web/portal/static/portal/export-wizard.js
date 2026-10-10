/* All form values remain local. User input travels to Python as JSON, never shell code. */
(function () {
  'use strict';
  const zones = ['UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Phoenix', 'America/Los_Angeles'];
  function text(value, name, required = true) {
    const result = String(value || '').trim();
    if ((required && !result) || result.length > 1024 || /[\x00-\x1f\x7f]/.test(result)) throw new Error(`Enter ${name} without line breaks (up to 1,024 characters).`);
    return result;
  }
  function wallTime(value) {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value)) throw new Error('Choose a complete start and end date/time.');
    const normalized = value.length === 16 ? value + ':00' : value;
    const date = new Date(normalized + 'Z');
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0,19) !== normalized) throw new Error('Choose valid calendar dates and times.');
    return normalized;
  }
  function buildArguments(values) {
    const player = text(values.player, 'the Minecraft player UUID');
    if (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(player)) throw new Error('Enter a Minecraft UUID with hyphens; an account name alone is not enough.');
    if (!zones.includes(values.timezone)) throw new Error('Choose the study timezone.');
    const start = wallTime(values.start), end = wallTime(values.end);
    if (end <= start) throw new Error('The end must be later than the start.');
    // Calendar comparison only; the exporter resolves actual instants and DST rules.
    if (new Date(end+'Z') - new Date(start+'Z') > 7*86400000) throw new Error('Export at most seven days at a time.');
    const output = text(values.output, 'an output JSON filename');
    if (!/\.json$/i.test(output)) throw new Error('The output filename must end in .json.');
    const args = [];
    for (const [flag, value] of [['config',text(values.config,'the local config path')],['catalog',text(values.catalog,'the reviewed catalog path')],['player',player],['label',text(values.label,'a learner label')],['timezone',values.timezone],['start',start],['end',end],['output',output]]) args.push(`--${flag}=${value}`);
    for (const flag of ['study','location','session-name','journal','roster']) {
      const value = text(values[flag], flag, false);
      if (value) args.push(`--${flag}=${value}`);
    }
    return args;
  }
  function renderScript(args, batch=false) {
    // ASCII JSON keeps Windows PowerShell 5.1's default pipeline encoding lossless.
    // JSON escapes line breaks, so input cannot terminate the literal here-string.
    const json = JSON.stringify(args, null, 2).replace(/[\u007f-\uffff]/g, c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
    return '# WHIMC Explorer: run in PowerShell from the extracted source project folder.\r\n' +
      '# Requires the prepared .venv, local configuration and reviewed catalog.\r\n' +
      '# Database credentials are prompted locally. Review paths and dates before running.\r\n' +
      "$exportArgumentsJson = @'\r\n" + json.replace(/\n/g,'\r\n') + "\r\n'@\r\n" +
      (batch ? "$exportArgumentsJson | & '.\\.venv\\Scripts\\python.exe' 'tools/export_batch.py'\r\n" : "$exportArgumentsJson | & '.\\.venv\\Scripts\\python.exe' '-c' 'import json, subprocess, sys; sys.exit(subprocess.call([sys.executable, sys.argv[1], *json.load(sys.stdin)]))' 'tools/export_session.py'\r\n") +
      "if ($LASTEXITCODE -ne 0) { throw 'An export failed. Read the messages above; only upload successfully generated JSON files.' }\r\n";
  }
  function buildScript(values) { return renderScript(buildArguments(values)); }
  function buildBatchScript(values, learners) {
    if (!learners.length || learners.length>50) throw new Error('Choose between 1 and 50 learners.');
    if (new Set(learners.map(a=>a.uuid.toLowerCase())).size !== learners.length) throw new Error('Each learner must be selected only once.');
    const base=text(values.output,'an output JSON filename');
    if (!/\.json$/i.test(base)) throw new Error('The base filename must end in .json.');
    const jobs=learners.map(a=>{
      const slug=a.name.replace(/[^A-Za-z0-9_-]/g,'-').slice(0,40) || 'learner';
      return buildArguments({...values,player:a.uuid,label:a.name,output:`${base.slice(0,-5)}-${slug}-${a.uuid.toLowerCase()}.json`});
    });
    return renderScript(jobs,true);
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = {buildScript,buildBatchScript}; return; }
  const form = document.getElementById('export-wizard');
  if (!form) return;
  const $ = id=>document.getElementById(id);
  let script = '';
  const learners=JSON.parse($('learner-roster').textContent), selected=new Set();
  function choices() {
    const query=$('learner-search').value.toLowerCase(); $('learner-choices').replaceChildren();
    for (const role of ['participant','operator','unknown']) {
      const group=learners.filter(a=>(['participant','operator'].includes(a.role)?a.role:'unknown')===role && a.name.toLowerCase().includes(query));
      if (!group.length) continue;
      const heading=document.createElement('h3');heading.textContent=role==='participant'?'Participants':role==='operator'?'Operators / test accounts':'Previously imported learners (role not recorded)';$('learner-choices').append(heading);
      for (const a of group) {
        const label=document.createElement('label'), box=document.createElement('input'), name=document.createElement('span');
        box.type='checkbox';box.checked=selected.has(a.uuid);name.textContent=a.name;
        box.addEventListener('change',()=>{box.checked?selected.add(a.uuid):selected.delete(a.uuid);invalidate();count();});
        label.append(box,name);$('learner-choices').append(label);
      }
    }
    count();
  }
  function count(){ $('learner-count').textContent=`${selected.size} selected · ${learners.length} available`; }
  $('learner-search').addEventListener('input',choices);
  $('learner-all').addEventListener('click',()=>{for(const a of learners)if(a.role==='participant')selected.add(a.uuid);invalidate();choices();});
  $('learner-clear').addEventListener('click',()=>{selected.clear();invalidate();choices();});
  $('learner-manual').addEventListener('change',()=>{
    const manual=$('learner-manual').checked;
    $('manual-learner').hidden=!manual;$('roster-picker').hidden=manual;
    for(const id of ['wizard-player','wizard-label'])$(id).required=manual;
    invalidate();
  });
  choices();
  function invalidate() { script=''; $('wizard-result').hidden=true; $('wizard-message').textContent=''; }
  form.addEventListener('input', invalidate);
  $('wizard-preset').addEventListener('change',()=>{
    invalidate();
    const date = $('wizard-start').value.slice(0,10) || $('wizard-end').value.slice(0,10);
    if (!date || $('wizard-preset').value === 'custom') return;
    const hours = $('wizard-preset').value === 'morning' ? ['09:00','12:00'] : ['13:00','16:00'];
    $('wizard-start').value = date+'T'+hours[0]; $('wizard-end').value = date+'T'+hours[1];
  });
  $('wizard-start').addEventListener('change',()=>{
    if ($('wizard-preset').value !== 'custom') $('wizard-preset').dispatchEvent(new Event('change'));
  });
  $('wizard-end').addEventListener('input',()=>{ $('wizard-preset').value='custom'; });
  form.addEventListener('submit', event=>{
    event.preventDefault(); invalidate();
    try {
      const values=Object.fromEntries(new FormData(form));
      script = $('learner-manual').checked ? buildScript(values) : buildBatchScript(values,learners.filter(a=>selected.has(a.uuid)));
      $('wizard-script').value=script; $('wizard-result').hidden=false;
      $('wizard-message').textContent='Script ready. Review it, then run it locally and upload the generated JSON.';
      $('wizard-script').focus();
    } catch (error) { $('wizard-message').textContent=error.message; }
  });
  $('wizard-copy').addEventListener('click',async()=>{
    if (!script) return;
    try { await navigator.clipboard.writeText(script); $('wizard-message').textContent='Copied. Paste into PowerShell in your extracted Explorer source folder.'; }
    catch (_) { $('wizard-script').focus(); $('wizard-script').select(); $('wizard-message').textContent='Select and copy the script below; automatic clipboard access is unavailable.'; }
  });
  $('wizard-download').addEventListener('click',()=>{
    if (!script) return;
    const url=URL.createObjectURL(new Blob([script],{type:'text/plain;charset=utf-8'})), link=document.createElement('a');
    link.href=url;link.download='export-session.ps1';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  form.hidden=false;
})();
