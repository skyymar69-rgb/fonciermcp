/* Lex Foncier — app.js v2.0 */
const API = 'https://app-production-71c1.up.railway.app';
const DPE_COLORS = {A:'#2DC653',B:'#79CC41',C:'#CADD28',D:'#FFEE08',E:'#F0A617',F:'#E07426',G:'#D62E2E'};

/* ── Cookie banner ── */
(function(){
  const k='lf_cookie';
  if(localStorage.getItem(k)) return;
  const b=document.getElementById('cookie-banner');
  if(!b) return;
  b.style.display='flex';
  document.getElementById('cookie-accept')?.addEventListener('click',()=>{localStorage.setItem(k,'1');b.style.display='none';});
  document.getElementById('cookie-refuse')?.addEventListener('click',()=>{localStorage.setItem(k,'0');b.style.display='none';});
})();

/* ── Nav mobile ── */
document.querySelector('.nav-mobile-btn')?.addEventListener('click',()=>{
  document.querySelector('.nav-main')?.classList.toggle('open');
});

/* ── Scroll animations ── */
const obs=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('visible');}),{threshold:0.1});
document.querySelectorAll('.animate-on-scroll,.fade-in').forEach(el=>obs.observe(el));

/* ── Formatters ── */
function fmtPrice(v){if(!v||v===0)return'—';return new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);}
function fmtM2(v){if(!v||v===0)return'—';return new Intl.NumberFormat('fr-FR').format(v)+' m²';}
function fmtDate(s){if(!s)return'—';return s.substring(0,10);}
function dpeBadge(l){if(!l)return'<span style="color:#999">—</span>';const c=DPE_COLORS[l]||'#999';return `<span style="background:${c};color:white;padding:0.1rem 0.5rem;border-radius:4px;font-weight:700;font-size:0.82rem">${l}</span>`;}

/* ── Demo widget (index.html) ── */
const demoWidget = document.getElementById('demo-container');
if(demoWidget){
  const searchBar = demoWidget.querySelector('.demo-search-bar');
  const input = demoWidget.querySelector('.demo-search-input');
  const btn = demoWidget.querySelector('.demo-search-btn');
  const spinner = demoWidget.querySelector('.demo-spinner');
  const empty = demoWidget.querySelector('.demo-empty');
  const results = demoWidget.querySelector('.demo-results');
  const errorDiv = demoWidget.querySelector('.demo-error');

  // Chips
  demoWidget.querySelectorAll('.demo-example-chip').forEach(chip=>{
    chip.addEventListener('click',()=>{
      input.value = chip.dataset.addr;
      runDemo(chip.dataset.addr);
    });
  });

  input?.addEventListener('keydown',e=>{ if(e.key==='Enter') runDemo(input.value); });
  btn?.addEventListener('click',()=>runDemo(input.value));

  async function runDemo(address){
    address = address?.trim();
    if(!address || address.length<5) return;
    
    // UI état chargement
    empty.style.display='none';
    results.style.display='none';
    errorDiv.textContent='';
    spinner.style.display='flex';
    btn.disabled=true;

    try {
      const r = await fetch(API+'/api/demo',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({address, dvf_radius:500})
      });
      const d = await r.json();
      
      if(!d.success){
        errorDiv.textContent = '⚠ ' + (d.erreur||'Adresse introuvable ou erreur API');
        spinner.style.display='none';
        btn.disabled=false;
        return;
      }
      
      renderResults(d, address);
    } catch(e){
      errorDiv.textContent = '⚠ Connexion impossible. Vérifiez votre réseau.';
    } finally {
      spinner.style.display='none';
      btn.disabled=false;
    }
  }

  function renderResults(d, address){
    const meta = d.meta||{};
    const cad = d.cadastre||{};
    const dvf = d.dvf||{};
    const plu = d.plu||{};
    const risks = d.risks||{};
    const dpe_data = d.dpe||{};
    const stats = dvf.stats||{};
    const ventes = (dvf.ventes_logements||dvf.ventes||[]).slice(0,5);
    const risques = risks.risques_gaspar||[];
    const dpes = (dpe_data.dpe_adresse||[]).slice(0,3);

    // Header
    const hdr = demoWidget.querySelector('.result-addr');
    const metaEl = demoWidget.querySelector('.result-meta');
    if(hdr) hdr.textContent = meta.address_normalized || address;
    if(metaEl) metaEl.textContent = `${meta.commune||''} · ${meta.code_postal||''} · ${meta.temps_secondes||''}s`;

    // ── CADASTRE ──
    const cEl = demoWidget.querySelector('.res-cadastre');
    if(cEl) cEl.innerHTML = cad.erreur
      ? `<p class="res-error">${cad.erreur}</p>`
      : `<div class="res-row"><span>Référence</span><b>${cad.reference||'—'}</b></div>
         <div class="res-row"><span>Section</span><b>${cad.section||'—'}</b></div>
         <div class="res-row"><span>Numéro</span><b>${cad.numero||'—'}</b></div>
         <div class="res-row"><span>Surface</span><b>${fmtM2(cad.surface_m2)}</b></div>
         <div class="res-row"><span>Commune</span><b>${cad.commune||meta.commune||'—'}</b></div>
         <div class="res-row"><span>Dép.</span><b>${cad.code_dep||'—'}</b></div>`;

    // ── PLU ──
    const pEl = demoWidget.querySelector('.res-plu');
    if(pEl){
      const typez = plu.type_zone||'';
      const colorMap={U:'#d4edda',AU:'#fff3cd',A:'#f8d7da',N:'#e2e3e5'};
      const textMap={U:'#1a7a37',AU:'#856404',A:'#721c24',N:'#383d41'};
      const bgColor = colorMap[typez.substring(0,2)] || '#f5f5f5';
      const txtColor = textMap[typez.substring(0,2)] || '#333';
      pEl.innerHTML = plu.erreur
        ? `<p class="res-error">${plu.erreur}</p>`
        : `<div style="margin-bottom:0.6rem"><span style="background:${bgColor};color:${txtColor};padding:0.2rem 0.7rem;border-radius:4px;font-weight:700;font-size:0.85rem">${plu.zone_principale||typez||'—'}</span></div>
           <div class="res-row"><span>Type zone</span><b>${typez||'—'}</b></div>
           <div class="res-row"><span>Constructibilité</span><b>${plu.constructibilite||'—'}</b></div>
           <div class="res-row"><span>Type doc.</span><b>${plu.document_urbanisme?.type||'—'}</b></div>
           <div class="res-row"><span>État</span><b>${plu.document_urbanisme?.etat||'—'}</b></div>
           <div class="res-row"><span>Date appro.</span><b>${plu.document_urbanisme?.date_approbation||'—'}</b></div>
           ${plu.document_urbanisme?.lien_reglement ? `<a href="${plu.document_urbanisme.lien_reglement}" target="_blank" class="res-link">↗ Règlement PDF</a>` : ''}`;
    }

    // ── DVF ──
    const dEl = demoWidget.querySelector('.res-dvf');
    if(dEl){
      let dvfHtml = '';
      if(dvf.erreur) {
        dvfHtml = `<p class="res-error">${dvf.erreur}</p>`;
      } else if(stats.prix_m2_median) {
        dvfHtml = `<div class="dvf-stats">
          <div class="dvf-stat-main">${fmtPrice(stats.prix_m2_median)}<small>/m²</small><span>Prix médian</span></div>
          <div class="dvf-stat"><span>Moyen</span><b>${fmtPrice(stats.prix_m2_moyen)}/m²</b></div>
          <div class="dvf-stat"><span>Min / Max</span><b>${fmtPrice(stats.prix_m2_min)} – ${fmtPrice(stats.prix_m2_max)}</b></div>
          <div class="dvf-stat"><span>Transactions</span><b>${stats.nb_transactions} ventes</b></div>
        </div>`;
        if(ventes.length){
          dvfHtml += `<table class="mini-table"><thead><tr><th>Date</th><th>Type</th><th>Surface</th><th>Prix</th><th>€/m²</th></tr></thead><tbody>${
            ventes.map(v=>`<tr>
              <td>${fmtDate(v.date)}</td>
              <td style="font-size:0.75rem">${(v.type_bien||'—').substring(0,25)}</td>
              <td>${fmtM2(v.surface_bati_m2||v.surface_terrain_m2)}</td>
              <td>${fmtPrice(v.valeur_euros)}</td>
              <td><b style="color:#B8860B">${fmtPrice(v.prix_m2)}</b></td>
            </tr>`).join('')
          }</tbody></table>`;
        }
      } else {
        dvfHtml = '<p class="res-empty">Aucune transaction dans ce rayon. Essayez avec une adresse plus centrale.</p>';
      }
      dEl.innerHTML = dvfHtml;
    }

    // ── RISQUES ──
    const rEl = demoWidget.querySelector('.res-risks');
    if(rEl){
      if(risks.erreur) {
        rEl.innerHTML = `<p class="res-error">${risks.erreur}</p>`;
      } else if(risques.length===0){
        rEl.innerHTML = '<div class="badge-ok">✓ Aucun risque identifié</div>';
      } else {
        rEl.innerHTML = `<div class="badge-warn">${risques.length} risque(s)</div>
          ${risques.slice(0,6).map(r=>`<div class="risque-row">
            <span class="risque-dot"></span>
            <span>${r.libelle||r.code_risque||'—'}</span>
          </div>`).join('')}
          ${risks.inondation?.present ? `<div class="risque-row"><span class="risque-dot"></span><span>Inondation — ${risks.inondation.nb_zones} zone(s)</span></div>` : ''}
          ${risks.argiles?.exposition ? `<div class="risque-row"><span class="risque-dot"></span><span>Argiles : ${risks.argiles.exposition}</span></div>` : ''}`;
      }
    }

    // ── DPE ──
    const deEl = demoWidget.querySelector('.res-dpe');
    if(deEl){
      if(dpe_data.erreur){
        deEl.innerHTML = `<p class="res-error">${dpe_data.erreur}</p>`;
      } else if(dpes.length){
        deEl.innerHTML = `<p style="font-size:0.75rem;color:#666;margin-bottom:0.5rem">${dpe_data.nb_dpe_proches||dpes.length} DPE dans un rayon de 200m</p>` +
          dpes.map(dp=>`<div class="dpe-row">
            ${dpeBadge(dp.etiquette_dpe)}${dpeBadge(dp.etiquette_ges)}
            <span style="font-size:0.78rem;color:#333;">${dp.type_batiment||'—'} · ${dp.surface_m2||'—'} m²</span>
          </div>`).join('');
      } else {
        deEl.innerHTML = '<p class="res-empty">Aucun DPE dans un rayon de 200m.</p>';
      }
    }

    results.style.display='block';
    
    // Bouton rapport
    const reportBtn = demoWidget.querySelector('.result-report-btn');
    if(reportBtn){
      reportBtn.href = `${API}/rapport?address=${encodeURIComponent(address)}`;
      reportBtn.style.display='inline-flex';
    }
  }
}

/* ── Hero search (mini widget) ── */
window.heroSet = function(a){
  const i=document.getElementById('hero-input');
  if(i){i.value=a; heroSearch();}
};
window.heroSearch = async function(){
  const inp=document.getElementById('hero-input');
  const btn=document.getElementById('hero-btn');
  const spin=document.getElementById('hero-spin');
  const res=document.getElementById('hero-result');
  const addr=inp?.value?.trim();
  if(!addr||addr.length<5) return;
  btn.disabled=true; spin.style.display='block'; res.innerHTML='';
  try{
    const r=await fetch(API+'/api/demo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:addr})});
    const d=await r.json();
    if(!d.success){res.innerHTML=`<p style="color:#e07426;font-size:0.82rem">${d.erreur||'Erreur'}</p>`;return;}
    const s=d.dvf?.stats||{}, plu=d.plu||{}, risks=d.risks||{};
    res.innerHTML=`<div style="margin-top:1rem;border-top:1px solid var(--c-border);padding-top:1rem">
      <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.75rem">${d.meta?.address_normalized||addr}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem;margin-bottom:0.75rem">
        <div class="mini-stat"><span>${s.prix_m2_median?fmtPrice(s.prix_m2_median)+'/m²':'—'}</span><label>DVF médiane</label></div>
        <div class="mini-stat"><span style="color:${plu.constructibilite==='Constructible'?'var(--c-green)':'var(--c-red)'}">${plu.zone_principale||plu.constructibilite||'—'}</span><label>PLU</label></div>
        <div class="mini-stat"><span style="color:${(risks.nb_risques||0)>0?'var(--c-gold)':'var(--c-green)'}">${risks.nb_risques||0} risque${(risks.nb_risques||0)>1?'s':''}</span><label>Géorisques</label></div>
      </div>
      <a href="${API}/rapport?address=${encodeURIComponent(addr)}" target="_blank" class="btn btn-primary" style="width:100%;text-align:center;display:block">📋 Voir le rapport complet</a>
    </div>`;
  }catch(e){res.innerHTML='<p style="color:#999;font-size:0.8rem">Connexion impossible.</p>';}
  finally{btn.disabled=false;spin.style.display='none';}
};
