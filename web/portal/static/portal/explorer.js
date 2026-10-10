"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const state = {sessions: [], page: 1, selected: null, data: null, controller: null, image: null, generation: 0, markers: []};
  const friendly = t => (t.name || t.id).replace(/§[0-9A-FK-ORX]/gi, '');
  const activityTitle = a => a.kind === 'observation' ? 'Observation' : `Science tool: ${a.tool}`;
  function showMarker(item) {
    const body = $('marker-body'); body.replaceChildren();
    $('marker-title').textContent = item.kind === 'observation' || item.kind === 'science_tool' ? activityTitle(item) : friendly(item);
    line(body, 'World', item.world);
    line(body, 'Location', `X ${item.x}, Y ${item.y}, Z ${item.z}`);
    if (item.time !== undefined) line(body, 'Recorded', date(item.time) + ' · ' + clock(item.time));
    if (item.text !== undefined) {
      const text = document.createElement('p'); text.className = 'evidence-text'; text.textContent = item.text; body.append(text);
    } else {
      const visits = state.data.metrics.proximity_visits.find(p => p.id === item.id && p.world === item.world);
      if (visits) line(body, 'Proximity', `${visits.estimated_dwell_seconds}s estimated dwell`);
      const clicks = state.data.bundle.events.filter(e => e.kind === 'npc_interaction' && e.target_id === item.id && e.world === item.world);
      if (item.kind === 'npc') line(body, 'Recorded interactions', state.data.bundle.availability.npc_interaction ? `${clicks.length} in the whole window${state.data.bundle.partial_sources?.includes('npc_interaction') ? ' · partial capture' : ''}` : 'Telemetry unavailable');
      line(body, 'Catalog ID', item.id);
    }
    if (!$('marker-dialog').open) $('marker-dialog').showModal();
    $('marker-close').focus();
  }
  function markerButton(item, title) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'marker-entry';
    button.textContent = title; button.addEventListener('click', () => showMarker(item)); return button;
  }
  const date = seconds => new Date(seconds * 1000).toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"});
  const clock = seconds => new Date(seconds * 1000).toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short"});
  function notice(message) { $("notice").textContent = message; $("notice").hidden = !message; }
  async function read(url, signal) {
    const response = await fetch(url, {credentials: "same-origin", signal, headers: {Accept: "application/json"}});
    if (!response.ok || !(response.headers.get("content-type") || "").includes("application/json")) {
      throw new Error("Could not load the session. Your NetID session may have expired; refresh and sign in again.");
    }
    return response.json();
  }
  function list() {
    const query = $("session-filter").value.trim().toLowerCase();
    $("session-list").replaceChildren();
    for (const s of state.sessions.filter(s => `${s.label} ${s.server} ${s.study || ''} ${s.location || ''} ${s.session_name || ''}`.toLowerCase().includes(query))) {
      const button = document.createElement("button");
      button.className = "session-item" + (s.id === state.selected ? " selected" : "");
      button.setAttribute("aria-pressed", String(s.id === state.selected));
      const name = document.createElement("strong"); name.textContent = s.label;
      const when = document.createElement("span"); when.textContent = date(s.start);
      const duration = document.createElement("span"); duration.textContent = `${s.server} · ${Math.round((s.end-s.start)/60)} min`;
      const study = document.createElement('span'); study.textContent = [s.study, s.location, s.session_name].filter(Boolean).join(' · ');
      button.append(name, study, when, duration); button.addEventListener("click", () => select(s));
      $("session-list").append(button);
    }
  }
  async function library() {
    try {
      const result = await read(document.body.dataset.sessionsUrl + "?page=" + state.page);
      state.sessions.push(...result.sessions);
      $("session-count").textContent = `${state.sessions.length} of ${result.total} sessions loaded`;
      $("load-more").hidden = !result.has_more;
      list();
      if (!state.selected && state.sessions.length) {
        const wanted = new URLSearchParams(location.search).get("session");
        const match = state.sessions.find(s => s.id === wanted);
        if (wanted && !match && result.has_more) { state.page++; await library(); return; }
        await select(match || state.sessions[0]);
      }
    } catch (error) { notice(error.message); }
  }
  async function select(session) {
    $('marker-dialog').close();
    state.controller?.abort(); state.controller = new AbortController();
    state.selected = session.id; list(); notice("");
    $("review").hidden = true; $("empty").hidden = false;
    try {
      const result = await read(session.url, state.controller.signal);
      if (state.selected !== session.id) return;
      state.data = result; $("empty").hidden = true; $("review").hidden = false;
      $("server-label").textContent = `SESSION REVIEW / ${session.server}`;
      $("player-label").textContent = session.label;
      $('study-label').textContent = [result.labels.study, result.labels.location, result.labels.session_name].filter(Boolean).join(' · ');
      $('edit-study-labels').hidden = !session.labels_url;
      if (session.labels_url) $('edit-study-labels').href = session.labels_url;
      $("session-time").textContent = `${date(session.start)} — ${date(session.end)} · ${result.bundle.session_source === "recorded" ? "Recorded session" : "Selected evaluation window"}`;
      $("download").href = session.download;
      $("world").replaceChildren();
      for (const name of Object.keys(result.bundle.worlds)) {
        const option = document.createElement("option"); option.value = name; option.textContent = name; $("world").append(option);
      }
      $("timeline").value = "1000";
      updateWorld();
      history.replaceState(null, "", "?session=" + encodeURIComponent(session.id));
    } catch (error) { if (error.name !== "AbortError") notice(error.message); }
  }
  function line(parent, title, value) {
    const row = document.createElement("div"); row.className = "quality-line";
    const bold = document.createElement("b"); bold.textContent = title + " "; row.append(bold, document.createTextNode(value)); parent.append(row);
  }
  function updateWorld() {
    $('marker-dialog').close();
    const {bundle: b, metrics: m} = state.data, world = $("world").value;
    const coverage = m.coverage[world];
    $("coverage").textContent = coverage.coverage_fraction === null ? "—" : Math.round(coverage.coverage_fraction*100) + "%";
    $("coverage-detail").textContent = `${coverage.visited_cells} of 100 sampled grid cells`;
    const pois = m.proximity_visits.filter(p => p.world === world);
    $("visits").textContent = coverage.position_samples ? `${pois.filter(p => p.qualifying_visit).length} / ${pois.length}` : "—";
    for (const [key, id, detailId] of [["npc_interaction", "npc", "npc-detail"], ["region_enter", "regions", "region-detail"]]) {
      const e = m.recorded_events[key];
      $(id).textContent = e === null ? "—" : `${e.unique_targets} / ${e.eligible_targets}`;
      $(detailId).textContent = e === null ? "Telemetry unavailable" : `${e.event_count} recorded events · ${e.partial ? "partial capture" : "all worlds"}`;
    }
    $("poi-list").replaceChildren();
    if (!pois.length) $("poi-list").textContent = "No waypoint or NPC locations in this world's catalog.";
    for (const p of pois) {
      const row = document.createElement("div"); row.className = "poi-row";
      const target = b.targets.find(t => t.id === p.id && t.world === p.world);
      const title = target ? markerButton(target, friendly(target)) : document.createTextNode(p.id);
      const detail = document.createElement("span"); detail.textContent = `${p.qualifying_visit === null ? "No samples" : p.qualifying_visit ? "Visited" : "Not qualified"} · ${p.estimated_dwell_seconds}s estimated dwell`;
      row.append(title, detail); $("poi-list").append(row);
    }
    $("quality").replaceChildren();
    line($("quality"), "Samples", `${m.quality.position_samples.toLocaleString()} · ${m.quality.path_breaks} path breaks`);
    line($("quality"), "Catalog", b.catalog_version);
    line($("quality"), "Metric", m.metric_version);
    line($("quality"), "Journey", m.recorded_events.journey_completed === null ? "Completion telemetry unavailable" : `${m.recorded_events.journey_completed.unique_targets} completed targets`);
    for (const [kind, title] of [['observation', 'Observations'], ['science_tool', 'Science measurements']]) {
      line($('quality'), title, b.activity_sources?.[kind] ? `${(b.activities || []).filter(a => a.kind === kind).length} records in export · logging completeness not asserted` : 'Not included in this export');
    }
    line($("quality"), "Excluded", `${m.quality.unknown_world_samples} samples in unknown worlds; ${m.quality.unknown_target_events} events at unknown targets`);
    for (const warning of b.warnings || []) line($("quality"), "Note", warning);
    const generation = ++state.generation; state.image = null;
    const image = b.worlds[world].image_png_base64;
    $("map-caption").textContent = image ? "Map supplied with this session" : "Coordinate view · no map background supplied";
    if (image) {
      const img = new Image();
      img.onload = () => { if (generation === state.generation) { state.image = img; draw(); } };
      img.onerror = () => { if (generation === state.generation) $("map-caption").textContent = "Map background could not be displayed"; };
      img.src = "data:image/png;base64," + image;
    }
    draw();
  }
  function draw() {
    if (!state.data) return;
    state.markers = [];
    const {bundle: b} = state.data, world = $("world").value, bounds = b.worlds[world];
    const canvas = $("map"), ctx = canvas.getContext("2d");
    const w = canvas.clientWidth, h = canvas.clientHeight, dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(w*dpr); canvas.height = Math.round(h*dpr); ctx.scale(dpr, dpr);
    ctx.fillStyle = "#142f3c"; ctx.fillRect(0, 0, w, h);
    const scale = Math.min((w-70)/(bounds.max_x-bounds.min_x), (h-50)/(bounds.max_z-bounds.min_z));
    const pw = (bounds.max_x-bounds.min_x)*scale, ph=(bounds.max_z-bounds.min_z)*scale;
    const left=(w-pw)/2, top=(h-ph)/2;
    const xy = p => [left+(p.x-bounds.min_x)*scale, top+(p.z-bounds.min_z)*scale];
    ctx.save(); ctx.beginPath(); ctx.rect(left, top, pw, ph); ctx.clip();
    if (state.image) { ctx.globalAlpha=.8; ctx.drawImage(state.image,left,top,pw,ph); ctx.globalAlpha=1; }
    const until = b.start + (b.end-b.start)*Number($("timeline").value)/1000;
    $("timeline-label").textContent = clock(until);
    const positions = [...new Map(b.positions.map(p=>[p.id,p])).values()].sort((a,c)=>a.time-c.time || (a.id<c.id?-1:a.id>c.id?1:0));
    if ($("show-grid").checked) {
      ctx.strokeStyle = "#afd8dd33"; ctx.lineWidth = .8;
      for(let i=0;i<=10;i++) { ctx.beginPath();ctx.moveTo(left+i*pw/10,top);ctx.lineTo(left+i*pw/10,top+ph);ctx.moveTo(left,top+i*ph/10);ctx.lineTo(left+pw,top+i*ph/10);ctx.stroke(); }
      const visited = new Set();
      for(const p of positions) { if(p.world!==world || p.time>until || p.x<bounds.min_x || p.x>=bounds.max_x || p.z<bounds.min_z || p.z>=bounds.max_z)continue;
        const x=Math.floor((p.x-bounds.min_x)/(bounds.max_x-bounds.min_x)*10),z=Math.floor((p.z-bounds.min_z)/(bounds.max_z-bounds.min_z)*10);visited.add(x+","+z); }
      ctx.fillStyle="#34c6b51c";for(const cell of visited){const [x,z]=cell.split(",").map(Number);ctx.fillRect(left+x*pw/10,top+z*ph/10,pw/10,ph/10);}
    }
    ctx.strokeStyle="#4fe4ce";ctx.lineWidth=2.4;ctx.lineJoin="round";ctx.lineCap="round";
    let previous=null, first=null, last=null;
    for(const p of positions){
      if(p.time>until)break;
      if(p.world!==world){previous=null;continue;}
      const [x,y]=xy(p);first ||= p;last=p;
      if(previous){const dt=p.time-previous.time,dist=Math.hypot(p.x-previous.x,p.y-previous.y,p.z-previous.z);
        if(!p.break_before && dt>0 && dt<=10 && dist<=20*dt){const [px,py]=xy(previous);ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(x,y);ctx.stroke();}}
      previous=p;
    }
    if($("show-pois").checked) for(const t of b.targets){if(t.world!==world || t.kind==="region")continue;
      const [x,y]=xy(t);ctx.fillStyle="#edbb62";ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#edbb6277";ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,t.radius*scale,0,Math.PI*2);ctx.stroke();
      if(x>=left && x<=left+pw && y>=top && y<=top+ph) state.markers.push({x,y,item:t});}
    if(first){const [x,y]=xy(first);ctx.fillStyle="#93eee0";ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();}
    if(last){const [x,y]=xy(last);ctx.fillStyle="#fff";ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#4fe4ce";ctx.lineWidth=3;ctx.stroke();}
    const activities = (b.activities || []).filter(a => a.world === world && a.time <= until && $(a.kind === 'observation' ? 'show-observations' : 'show-tools').checked).sort((a,c)=>a.time-c.time);
    for (const a of activities) {
      const [x,y] = xy(a); ctx.fillStyle = a.kind === 'observation' ? '#8bcaff' : '#e4a2ff';
      ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#142f3c';ctx.lineWidth=2;ctx.stroke();
      if(x>=left && x<=left+pw && y>=top && y<=top+ph) state.markers.push({x,y,item:a});
    }
    $('activity-list').replaceChildren();
    $('activity-count').textContent = activities.length ? `${activities.length} records visible at this time. Select a dot or an entry below.` : 'No activity records at this time with these filters. Older exports may not include this evidence.';
    for (const a of activities.slice(0, 100)) $('activity-list').append(markerButton(a, `${clock(a.time)} · ${activityTitle(a)}`));
    if (activities.length > 100) $('activity-count').textContent += ' The list shows the first 100; all in-bounds dots remain selectable.';
    ctx.restore();ctx.strokeStyle="#9cc3cb55";ctx.lineWidth=1;ctx.strokeRect(left,top,pw,ph);
  }
  $("session-filter").addEventListener("input",list);
  $("load-more").addEventListener("click",async()=>{$("load-more").disabled=true;state.page++;await library();$("load-more").disabled=false;});
  $("world").addEventListener("change",updateWorld);
  for(const id of ["show-pois","show-grid","show-observations","show-tools","timeline"])$(id).addEventListener("input",draw);
  $('marker-close').addEventListener('click', () => $('marker-dialog').close());
  $('map').addEventListener('click', event => {
    const rect = $('map').getBoundingClientRect();
    const hits = state.markers.filter(m => Math.hypot(m.x-(event.clientX-rect.left),m.y-(event.clientY-rect.top)) <= 12);
    if (hits.length === 1) showMarker(hits[0].item);
    else if (hits.length > 1) {
      $('marker-title').textContent = 'Choose evidence at this location'; $('marker-body').replaceChildren();
      for (const {item} of hits) $('marker-body').append(markerButton(item, item.time === undefined ? friendly(item) : `${clock(item.time)} · ${activityTitle(item)}`));
      $('marker-dialog').showModal();
    }
  });
  new ResizeObserver(draw).observe($("map"));
  library();
})();
