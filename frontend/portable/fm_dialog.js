/* TS-FIX-07: accessible, club-themed confirmation and non-blocking notifications. */
(() => {
  'use strict';
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let current = null;
  function confirm(message, title = 'Confirm action') {
    if (current) return Promise.resolve(false);
    return new Promise(resolve => {
      const focusBefore = document.activeElement;
      const shell = document.createElement('div');
      shell.className='fm-action-backdrop';
      shell.innerHTML=`<section class="fm-action-dialog" role="dialog" aria-modal="true" aria-labelledby="fm-action-title" aria-describedby="fm-action-text">
        <div class="fm-action-eyebrow">MANAGER DECISION</div><h2 id="fm-action-title">${escape(title)}</h2>
        <p id="fm-action-text">${escape(message)}</p>
        <div class="fm-action-buttons"><button type="button" data-fm-action-cancel>Cancel</button><button type="button" class="fm-action-approve" data-fm-action-yes>Confirm</button></div></section>`;
      let done = false;
      function finish(value) {
        if (done) return; done = true;
        shell.remove();document.removeEventListener('keydown',keyHandler);
        current=null;
        if(focusBefore?.isConnected) focusBefore.focus();
        resolve(value);
      }
      function keyHandler(event) {
        if(event.key==='Escape'){event.preventDefault();finish(false);}
        else if(event.key==='Tab') {
          const nodes=[...shell.querySelectorAll('button')]; const i=nodes.indexOf(document.activeElement);
          if(event.shiftKey && i<=0){event.preventDefault();nodes[nodes.length-1].focus();}
          else if(!event.shiftKey && i===nodes.length-1){event.preventDefault();nodes[0].focus();}
        }
      }
      shell.addEventListener('click',event=>{if(event.target===shell)finish(false);});
      shell.querySelector('[data-fm-action-cancel]').addEventListener('click',()=>finish(false));
      shell.querySelector('[data-fm-action-yes]').addEventListener('click',()=>finish(true));
      current=shell;document.body.append(shell);document.addEventListener('keydown',keyHandler);
      shell.querySelector('[data-fm-action-cancel]').focus();
    });
  }
  function notify(message, kind='error') {
    let region=document.getElementById('fm-action-toasts');
    if(!region){region=document.createElement('div');region.id='fm-action-toasts';region.className='fm-action-toasts';region.setAttribute('aria-live','polite');document.body.append(region);}
    const toast=document.createElement('div');toast.className='fm-action-toast '+(kind==='success'?'is-success':'is-error');
    const text=document.createElement('span');text.textContent=String(message);toast.append(text);
    const close=document.createElement('button');close.type='button';close.setAttribute('aria-label','Dismiss notice');close.textContent='×';close.onclick=()=>toast.remove();toast.append(close);
    region.append(toast);
    // User controls dismissal. Avoid timers and forced interrupted reading.
    while(region.children.length>4)region.firstElementChild.remove();
  }
  window.FMDialog=Object.freeze({confirm,notify});
})();
