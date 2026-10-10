/* Upload one bounded bundle per request; keep per-file results for safe retries. */
(() => {
  'use strict';
  const form=document.getElementById('upload-form'), files=document.getElementById('bundle');
  if(!form) return;
  files.multiple=true;
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const selected=[...files.files], summary=document.getElementById('upload-summary'), results=document.getElementById('upload-results');
    if(!selected.length || selected.length>50){summary.textContent='Choose between 1 and 50 JSON files.';return;}
    const button=form.querySelector('button[type=submit]');button.disabled=true;files.disabled=true;results.replaceChildren();
    let added=0, duplicates=0, failed=0, attempted=0;
    try {
      for(const file of selected){
        attempted++;summary.textContent=`Importing ${attempted} of ${selected.length}…`;
        const row=document.createElement('li');results.append(row);
        if(file.size>8*1024*1024){failed++;row.textContent=`${file.name}: exceeds 8 MB; not uploaded.`;continue;}
        const data=new FormData();data.append('csrfmiddlewaretoken',form.querySelector('[name=csrfmiddlewaretoken]').value);data.append('bundle',file);
        try {
          const response=await fetch(form.action || location.href,{method:'POST',body:data,credentials:'same-origin',headers:{Accept:'application/json'}});
          if(!(response.headers.get('content-type')||'').includes('application/json')) throw new Error('Sign-in may have expired or the server rejected the request. Refresh and sign in; reselecting these files is safe.');
          const result=await response.json();
          if(!response.ok){failed++;row.textContent=`${file.name}: ${result.error || 'Import failed.'}`;if(response.status!==400)break;continue;}
          result.created?added++:duplicates++;
          row.textContent=`${file.name}: ${result.created?'Imported':'Already imported'}. `;
          const link=document.createElement('a');link.href=result.url;link.textContent='View session';row.append(link);
        } catch(error){failed++;row.textContent=`${file.name}: ${error.message}`;break;}
      }
      summary.textContent=`Finished: ${added} imported, ${duplicates} already present, ${failed} failed, ${selected.length-attempted} not attempted. Retry failed or unattempted files; successful imports are retained.`;
    } finally {button.disabled=false;files.disabled=false;}
  });
})();
