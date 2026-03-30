/* FoncierMCP — Shared JS */

const API = 'https://app-production-71c1.up.railway.app';

// ── Nav scroll effect ──
window.addEventListener('scroll', () => {
  const nav = document.querySelector('.site-nav');
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 10);
});

// ── Cookie Banner ──
function initCookies() {
  const banner = document.getElementById('cookie-banner');
  if (!banner) return;
  const accepted = localStorage.getItem('fm_cookies_accepted');
  if (!accepted) {
    setTimeout(() => banner.classList.add('visible'), 1500);
  }
  document.getElementById('cookie-accept')?.addEventListener('click', () => {
    localStorage.setItem('fm_cookies_accepted', 'all');
    banner.classList.remove('visible');
  });
  document.getElementById('cookie-refuse')?.addEventListener('click', () => {
    localStorage.setItem('fm_cookies_accepted', 'essential');
    banner.classList.remove('visible');
  });
}

// ── Mobile Nav ──
function initMobileNav() {
  const btn = document.querySelector('.nav-mobile-btn');
  const main = document.querySelector('.nav-main');
  if (!btn || !main) return;
  let open = false;
  btn.addEventListener('click', () => {
    open = !open;
    btn.textContent = open ? '✕' : '☰';
    if (open) {
      main.style.cssText = 'display:flex;flex-direction:column;position:fixed;top:64px;left:0;right:0;background:var(--c-bg);border-top:1px solid var(--c-border);padding:1rem;z-index:999;';
    } else {
      main.style.cssText = '';
    }
  });
}

// ── Demo Engine ──
function initDemo(containerId) {
  const container = document.getElementById(containerId || 'demo-container');
  if (!container) return;
  const input = container.querySelector('.demo-search-input');
  const btn = container.querySelector('.demo-search-btn');
  const spinner = container.querySelector('.demo-spinner');
  const results = container.querySelector('.demo-results');
  const error = container.querySelector('.demo-error');
  const emptyState = container.querySelector('.demo-empty');
  if (!input || !btn) return;
  container.querySelectorAll('.demo-example-chip').forEach(chip => {
    chip.addEventListener('click', () => { input.value = chip.dataset.addr; runAnalysis(); });
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter') runAnalysis(); });
  btn.addEventListener('click', runAnalysis);
  async function runAnalysis() {
    const addr = input.value.trim();
    if (addr.length < 5) return;
    btn.disabled = true;
    if (spinner) spinner.classList.add('on');
    if (results) results.style.display = 'none';
    if (error) error.style.display = 'none';
    if (emptyState) emptyState.style.display = 'none';
    try {
      const r = await fetch(API + '/api/demo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: addr }) });
      const data = await r.json();
      if (!data.success) { if (error) { error.textContent = data.error || 'Adresse introuvable.'; error.style.display = 'block'; } return; }
      renderResults(container, data);
      if (results) results.style.display = 'block';
    } catch (e) {
      if (error) { error.textContent = 'Connexion impossible.'; error.style.display = 'block'; }
    } finally {
      btn.disabled = false;
      if (spinner) spinner.classList.remove('on');
    }
  }
}

function fmt(n) { return n != null ? Number(n).toLocaleString('fr-FR') + ' €' : '—'; }
function fmtm2(n) { return n != null ? Number(n).toLocaleString('fr-FR') + ' €/m²' : '—'; }
function renderResults(container,d){const c=d.coordinates||{};const ra=container.querySelector('.result-addr');const rm=container.querySelector('.result-meta');if(ra)ra.textContent=d.address||'-';if(rm)rm.textContent=[c.lat?c.lat.toFixed(5)+', '+c.lon.toFixed(5):'',d.geocoding_score?'Confiance '+Math.round(d.geocoding_score*100)+'%':''].filter(Boolean).join(' . ');const p=d.cadastre||{};const cad=container.querySelector('.res-cadastre');if(cad)cad.innerHTML=p.parcel_id?'<div class="kv-list"><div class="kv-row"><span class="kv-label">Ref</span><span class="kv-value">'+p.parcel_id+'</span></div><div class="kv-row"><span class="kv-label">Surface</span><span class="kv-value">'+(p.surface_m2?p.surface_m2.toLocaleString('fr-FR')+' m2':'-')+'</span></div></div>':'<div style="color:var(--c-muted)">Parcelle non localisee</div>';const pluEl=container.querySelector('.res-plu');if(pluEl){const plu=d.plu||{};const cs=plu.constructibilite||{};const bmap={'Constructible':'badge-green','Non constructible':'badge-red','Constructible sous conditions':'badge-gold'};const zones=(plu.zones||[]).slice(0,2);const doc=plu.document_urbanisme||{};pluEl.innerHTML='<div style="margin-bottom:0.75rem"><span class="badge '+(bmap[cs.statut]||'badge-gray')+'">'+( cs.statut||'Inconnu')+'</span></div>'+(cs.detail?'<div style="font-size:0.82rem;color:var(--c-muted)">'+cs.detail+'</div>':'')+zones.map(z=>'<div style="font-size:0.78rem;color:var(--c-muted)"><b>'+(z.libelle||z.type_zone||'')+'</b></div>').join('')+(doc.commune?'<div style="font-family:var(--mono);font-size:0.62rem;color:var(--c-muted);margin-top:0.5rem">'+(doc.type_doc||'PLU')+' - '+doc.commune+'</div>':'');}const dvfEl=container.querySelector('.res-dvf');if(dvfEl){const dv=d.dvf||{};const st=dv.stats||{};if(st.prix_m2_median){const ventes=(dv.ventes||[]).slice(0,5);const fmt=n=>n!=null?Number(n).toLocaleString('fr-FR')+' euros':'-';const fmtm=n=>n!=null?Number(n).toLocaleString('fr-FR')+' euros/m2':'-';dvfEl.innerHTML='<div class="price-hero"><div class="price-hero-val">'+fmtm(st.prix_m2_median)+'</div><div class="price-hero-unit">mediane rayon '+dv.radius_m+'m</div></div><div class="price-stats"><div class="price-stat"><div class="price-stat-val">'+fmtm(st.prix_m2_min)+'</div><div class="price-stat-label">Min</div></div><div class="price-stat"><div class="price-stat-val">'+fmtm(st.prix_m2_moyen)+'</div><div class="price-stat-label">Moyen</div></div><div class="price-stat"><div class="price-stat-val">'+fmtm(st.prix_m2_max)+'</div><div class="price-stat-label">Max</div></div></div><div style="font-size:0.72rem;color:var(--c-muted);margin-bottom:0.75rem;font-family:var(--mono)">'+st.nb_transactions+' transactions</div><div class="tx-list">'+ventes.map(v=>'<div class="tx-row"><span class="tx-date">'+(v.date||'').substring(0,7)+'</span><span class="tx-type">'+(v.type||'Bien')+(v.surface_m2?' '+v.surface_m2+' m2':'')+'</span><span class="tx-price">'+fmt(v.prix_total)+'</span></div>').join('')+'</div>';}else{dvfEl.innerHTML='<div style="color:var(--c-muted)">Aucune transaction dans ce rayon.</div>';}}const riskEl=container.querySelector('.res-risks');if(riskEl){const rk=d.risks||{};const rl=(rk.risques||[]).slice(0,8);riskEl.innerHTML=rl.length?'<div style="font-size:0.72rem;color:var(--c-muted);margin-bottom:0.5rem">'+rk.synthese+'</div><div class="risk-list">'+rl.map(r=>'<div class="risk-item"><div class="risk-dot"></div><span>'+r.type+'</span></div>').join('')+'</div>':'<div class="no-risk">OK - Aucun risque majeur</div>';}const dpeEl=container.querySelector('.res-dpe');if(dpeEl){const dp=d.dpe||{};const se=dp.stats_etiquettes||{};const ordre=['A','B','C','D','E','F','G'];const max=Math.max(...Object.values(se),1);if(Object.keys(se).length){dpeEl.innerHTML='<div style="font-size:0.72rem;color:var(--c-muted);margin-bottom:0.75rem">'+(dp.nb||0)+' DPE dans la commune</div><div class="dpe-bars">'+ordre.filter(e=>se[e]).map(e=>{const h=Math.max(8,Math.round((se[e]/max)*52));return'<div class="dpe-bar-col"><div class="dpe-bar d'+e+'" style="height:'+h+'px"></div><div class="dpe-bar-label">'+e+'</div><div class="dpe-bar-count">'+se[e]+'</div></div>';}).join('')+'</div>';}else{dpeEl.innerHTML='<div style="color:var(--c-muted)">Aucun DPE disponible.</div>';}}}document.addEventListener('DOMContentLoaded',()=>{initCookies();initMobileNav();initDemo();const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){e.target.style.opacity='1';e.target.style.transform='translateY(0)';}});},{threshold:0.08});document.querySelectorAll('.animate-on-scroll').forEach(el=>{el.style.opacity='0';el.style.transform='translateY(24px)';el.style.transition='opacity 0.6s ease, transform 0.6s ease';observer.observe(el);});});
