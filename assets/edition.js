
(function(){
  const B=document.body;
  function store(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  function load(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function setMode(m){
    store('edmode',m);                                  // zachovej preferenci uživatele
    var eff=(m==='teige'&&!B.classList.contains('has-teige'))?'dipl':m;  // Teige jen kde dává smysl
    B.classList.remove('mode-dipl','mode-norm','mode-teige');B.classList.add('mode-'+eff);
    for(const r of document.querySelectorAll('input[name=mode]'))r.checked=(r.value===eff);}
  function setLayout(l){
    B.classList.remove('layout-lined','layout-flow');B.classList.add('layout-'+l);
    for(const r of document.querySelectorAll('input[name=layout]'))r.checked=(r.value===l);
    store('edlayout',l);}
  function setApp(on){
    B.classList.toggle('app-off',!on);
    const c=document.getElementById('appToggle');if(c)c.checked=on;
    store('edapp',on?'1':'0');}
  document.addEventListener('DOMContentLoaded',function(){
    const sm=load('edmode');if(sm)setMode(sm);
    const sl=load('edlayout');if(sl)setLayout(sl);
    const sa=load('edapp');if(sa!==null)setApp(sa==='1');
    for(const r of document.querySelectorAll('input[name=mode]'))r.addEventListener('change',()=>setMode(r.value));
    for(const r of document.querySelectorAll('input[name=layout]'))r.addEventListener('change',()=>setLayout(r.value));
    const c=document.getElementById('appToggle');if(c)c.addEventListener('change',()=>setApp(c.checked));
    let tt;
    function toast(msg){
      let el=document.getElementById('ed-toast');
      if(!el){el=document.createElement('div');el.id='ed-toast';document.body.appendChild(el);}
      el.textContent=msg;el.classList.add('show');
      clearTimeout(tt);tt=setTimeout(()=>el.classList.remove('show'),1900);}
    document.addEventListener('click',function(e){
      const a=e.target.closest('a.lno');if(!a)return;
      e.preventDefault();
      const id=a.getAttribute('href').slice(1);
      const wrap=a.closest('.lines');const fol=wrap?wrap.getAttribute('data-folio'):'';
      const ref='fol. '+fol+', ř. '+a.getAttribute('data-n');
      const url=location.href.split('#')[0]+'#'+id;
      try{history.replaceState(null,'','#'+id)}catch(_){location.hash=id;}
      const t=document.getElementById(id);
      if(t){t.classList.remove('flash');void t.offsetWidth;t.classList.add('flash');}
      const cite=ref+' — '+url;
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(cite).then(()=>toast('Zkopírováno: '+ref)).catch(()=>toast(ref));
      }else toast(ref);
    });
    document.addEventListener('keydown',function(e){
      if(e.target.tagName==='INPUT')return;
      if(e.key==='ArrowLeft'){const a=document.querySelector('.pager .prev');if(a&&!a.hidden)location.href=a.getAttribute('href');}
      if(e.key==='ArrowRight'){const a=document.querySelector('.pager .next');if(a&&!a.hidden)location.href=a.getAttribute('href');}
    });
  });
})();
