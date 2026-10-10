"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const colors = ['#55e4cf','#ffb454','#b0a5ff','#ff8496','#70c9ff','#d8e77b','#f0a6e6','#ffffff'];
  const patterns = [[],[8,4],[3,4],[12,4,3,4],[14,5],[2,6],[8,3,2,3],[16,3,2,3,2,3]];
  let sessions = [], selectionWindow = null, result = null, background = null, generation = 0, visible = new Set();
  function notice(text) { $('comparison-notice').textContent = text; $('comparison-notice').hidden = !text; }
  function clearResult() { generation++; result = null; background = null; $('comparison-result').hidden = true; }
  function invalidate() { clearResult(); $('selection').hidden = true; selectionWindow = null; }
  function local(seconds) { const d = new Date(seconds*1000); return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,19); }
  function times() {
    const start = Math.floor(new Date($('range-start').value).getTime()/1000), end = Math.floor(new Date($('range-end').value).getTime()/1000);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) throw new Error('Choose a valid start and end time.');
    return {start, end};
  }
  async function read(url) {
    const response = await fetch(url, {credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Could not read comparison data. Refresh and sign in again.');
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Could not load comparison data.'); return data;
  }
  function options(id, values) {
    $(id).replaceChildren(); for (const value of [...new Set(values)].sort()) { const option = document.createElement('option'); option.value = value; option.textContent = value; $(id).append(option); }
  }
  function worlds() {
    clearResult(); options('compare-world', sessions.filter(s => s.server_id === $('compare-server').value).flatMap(s => s.world_names)); players();
  }
  function players() {
    clearResult(); $('player-choices').replaceChildren();
    const groups = new Map();
    for (const s of sessions.filter(s => s.server_id === $('compare-server').value && s.world_names.includes($('compare-world').value))) {
      if (!groups.has(s.player_uuid)) groups.set(s.player_uuid, []); groups.get(s.player_uuid).push(s);
    }
    for (const [uuid, group] of groups) {
      const label = document.createElement('label'); label.className = 'player-choice';
      const input = document.createElement('input'); input.type = 'checkbox'; input.value = uuid; input.dataset.ids = JSON.stringify(group.map(s=>s.id)); input.addEventListener('change',clearResult);
      const text = document.createElement('span'); text.textContent = [...new Set(group.map(s=>s.player_label))].join(' / ');
      const detail = document.createElement('small'); detail.textContent = `${group.length} imported session(s) · ${[...new Set(group.map(s=>s.session_name).filter(Boolean))].join(' / ')} · ${uuid}`; text.append(detail); label.append(input,text); $('player-choices').append(label);
    }
  }
  async function find(event) {
    event?.preventDefault(); invalidate(); notice(''); const token = generation;
    try {
      const w = times(), query = new URLSearchParams({...w,server:$('server-filter').value.trim(),study:$('study-filter').value,location:$('location-filter').value});
      const data = await read(document.body.dataset.optionsUrl+'?'+query);
      if (token !== generation) return;
      sessions = data.sessions; selectionWindow = w;
      if (!sessions.length) { notice('No imported sessions overlap this range. Import the completed player sessions first.'); return; }
      options('compare-server', sessions.map(s=>s.server_id)); options('known-servers', sessions.map(s=>s.server_id));
      $('selection').hidden = false; worlds();
    } catch(error) { if(token === generation) notice(error.message); }
  }
  async function compare() {
    clearResult(); notice(''); const token = generation;
    try {
      if (!selectionWindow) throw new Error('Find sessions for this date range first.');
      const chosen = [...$('player-choices').querySelectorAll('input:checked')];
      if (!chosen.length || chosen.length > 8) throw new Error('Select between 1 and 8 players.');
      const ids = chosen.flatMap(c=>JSON.parse(c.dataset.ids)); if(ids.length>20) throw new Error('More than 20 sessions selected. Narrow the date range or select fewer players.');
      const query = new URLSearchParams({...selectionWindow,world:$('compare-world').value}); ids.forEach(id=>query.append('id',id));
      const data = await read(document.body.dataset.pathsUrl+'?'+query); if(token !== generation) return;
      result=data; visible = new Set(data.players.map(p=>p.uuid)); $('comparison-result').hidden=false;
      $('comparison-world').textContent=`${data.server} / ${data.world}`;
      $('comparison-window').textContent = `${new Date(data.start*1000).toLocaleString()} — ${new Date(data.end*1000).toLocaleString()} · ${data.samples.toLocaleString()} unique samples`;
      $('route-legend').replaceChildren();
      data.players.forEach((p,i)=>{
        const label=document.createElement('label'), input=document.createElement('input'), swatch=document.createElement('i'); input.type='checkbox'; input.checked=true;
        input.addEventListener('change',()=>{input.checked ? visible.add(p.uuid) : visible.delete(p.uuid); draw();});
        swatch.className=`route-swatch route-${i}`;label.append(input,swatch,document.createTextNode(`${p.label} · ${p.samples} samples`));$('route-legend').append(label);
      });
      $('comparison-caption').textContent = data.map.image_png_base64 ? 'Shared calibrated background' : 'Coordinate view · no map background supplied';
      if(data.map.image_png_base64){const img=new Image();img.onload=()=>{if(token===generation){background=img;draw();}};img.onerror=()=>{if(token===generation)$('comparison-caption').textContent='Map background could not be displayed';};img.src='data:image/png;base64,'+data.map.image_png_base64;}
      draw();
    } catch(error) {if(token===generation)notice(error.message);}
  }
  function draw() {
    if(!result)return; const canvas=$('comparison-map'), ctx=canvas.getContext('2d'), w=canvas.clientWidth,h=canvas.clientHeight,dpr=Math.min(devicePixelRatio||1,2),b=result.map;
    canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.scale(dpr,dpr);ctx.fillStyle='#142f3c';ctx.fillRect(0,0,w,h);
    const scale=Math.min((w-60)/(b.max_x-b.min_x),(h-50)/(b.max_z-b.min_z)),pw=(b.max_x-b.min_x)*scale,ph=(b.max_z-b.min_z)*scale,left=(w-pw)/2,top=(h-ph)/2;
    const xy=p=>[left+(p.x-b.min_x)*scale,top+(p.z-b.min_z)*scale];
    ctx.save();ctx.beginPath();ctx.rect(left,top,pw,ph);ctx.clip();
    if(background){ctx.globalAlpha=.75;ctx.drawImage(background,left,top,pw,ph);ctx.globalAlpha=1;}
    ctx.strokeStyle='#afd8dd33';ctx.lineWidth=.8;for(let i=0;i<=10;i++){ctx.beginPath();ctx.moveTo(left+i*pw/10,top);ctx.lineTo(left+i*pw/10,top+ph);ctx.moveTo(left,top+i*ph/10);ctx.lineTo(left+pw,top+i*ph/10);ctx.stroke();}
    result.players.forEach((p,i)=>{if(!visible.has(p.uuid))return;ctx.strokeStyle=colors[i];ctx.fillStyle=colors[i];ctx.lineWidth=2.5;ctx.setLineDash(patterns[i]);
      for(const segment of p.segments){ctx.beginPath();segment.forEach((point,j)=>{const [x,y]=xy(point);j?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();const [x,y]=xy(segment[0]);ctx.beginPath();ctx.arc(x,y,3.5,0,Math.PI*2);ctx.fill();}
    });ctx.restore();ctx.setLineDash([]);ctx.strokeStyle='#9cc3cb55';ctx.strokeRect(left,top,pw,ph);
  }
  $('range-form').addEventListener('submit',find);$('compare-server').addEventListener('change',worlds);$('compare-world').addEventListener('change',players);$('compare-submit').addEventListener('click',compare);
  for(const id of ['range-start','range-end','server-filter','study-filter','location-filter'])$(id).addEventListener('input',invalidate);
  new ResizeObserver(draw).observe($('comparison-map'));
  $('timezone').textContent=`Times use your browser timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}. The end time is excluded.`;
  $('use-week').addEventListener('click',()=>{
    if(!$('study-week').value){notice('Choose the first date of the study week.');return;}
    const start=new Date($('study-week').value+'T00:00:00'), end=new Date(start);end.setDate(end.getDate()+7);
    $('range-start').value=local(start.getTime()/1000);$('range-end').value=local(end.getTime()/1000);find();
  });
  read(document.body.dataset.optionsUrl).then(data=>{
    for(const [id,items] of [['study-filter',data.studies],['location-filter',data.locations]]) for(const value of items){const option=document.createElement('option');option.value=value;option.textContent=value;$(id).append(option);}
    if(data.latest){$('range-start').value=local(data.latest-86400);$('range-end').value=local(data.latest);return find();}notice('Import a session to begin comparing paths.');}).catch(error=>notice(error.message));
})();
