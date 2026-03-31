"""
rapport.py — Génère un rapport foncier HTML professionnel imprimable
Sources officielles : BAN, IGN, DGFiP, GPU, Géorisques, ADEME
"""
from datetime import datetime

COLORS = {
    "A": "#2DC653", "B": "#79CC41", "C": "#CADD28",
    "D": "#FFEE08", "E": "#F0A617", "F": "#E07426", "G": "#D62E2E"
}

def _fmt_price(v):
    if not v: return "—"
    return f"{v:,.0f} €".replace(",", " ")

def _fmt_m2(v):
    if not v: return "—"
    return f"{v:,.0f} m²".replace(",", " ")

def _dpe_badge(label):
    c = COLORS.get(label, "#999")
    return f'<span class="dpe-badge" style="background:{c}">{label}</span>'

def _risque_badge(count):
    if count == 0: return '<span class="badge-ok">✓ Aucun risque identifié</span>'
    if count <= 2: return f'<span class="badge-warn">{count} risque(s) identifié(s)</span>'
    return f'<span class="badge-danger">{count} risques identifiés</span>'

def generate_rapport(data: dict) -> str:
    meta = data.get("meta", {})
    cadastre = data.get("cadastre", {})
    dvf = data.get("dvf", {})
    plu = data.get("plu", {})
    risks = data.get("risks", {})
    dpe = data.get("dpe", {})
    adresse = data.get("adresse", {})
    
    stats = dvf.get("stats", {})
    ventes = dvf.get("ventes_logements", dvf.get("ventes", []))[:10]
    risques_list = risks.get("risques_gaspar", [])
    dpe_proches = dpe.get("dpe_adresse", [])[:5]
    
    date_rapport = datetime.now().strftime("%d/%m/%Y à %H:%M")
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rapport Foncier — {meta.get('address_normalized','')}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1a1a1a; background: #f5f5f0; }}
.page {{ max-width: 900px; margin: 0 auto; background: white; padding: 2.5rem; }}

/* HEADER */
.report-header {{ display:flex; justify-content:space-between; align-items:flex-start; padding-bottom:1.5rem; border-bottom:3px solid #B8860B; margin-bottom:2rem; }}
.report-logo {{ font-size:1.4rem; font-weight:700; color:#B8860B; letter-spacing:-0.02em; }}
.report-logo span {{ color:#1a1a1a; }}
.report-meta {{ text-align:right; font-size:0.78rem; color:#666; line-height:1.8; }}
.report-title {{ margin-bottom:1.5rem; }}
.report-title h1 {{ font-size:1.5rem; font-weight:700; color:#1a1a1a; margin-bottom:0.35rem; }}
.report-title .subtitle {{ font-size:0.85rem; color:#666; }}

/* RÉSUMÉ EXÉCUTIF */
.exec-summary {{ background:#fffbf0; border:2px solid #B8860B; border-radius:8px; padding:1.5rem; margin-bottom:2rem; display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; }}
.exec-item {{ text-align:center; }}
.exec-val {{ font-size:1.6rem; font-weight:700; color:#B8860B; line-height:1; display:block; margin-bottom:0.25rem; }}
.exec-label {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:0.08em; color:#666; }}

/* SECTIONS */
.section {{ margin-bottom:2rem; page-break-inside:avoid; }}
.section-header {{ display:flex; align-items:center; gap:0.75rem; padding:0.6rem 1rem; background:#1a1a1a; color:white; border-radius:6px 6px 0 0; margin-bottom:0; }}
.section-icon {{ font-size:1rem; }}
.section-title {{ font-size:0.85rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; }}
.section-source {{ margin-left:auto; font-size:0.65rem; color:rgba(255,255,255,0.6); }}
.section-body {{ border:1px solid #e0e0e0; border-top:none; border-radius:0 0 6px 6px; padding:1.25rem; }}

/* TABLES */
.data-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0; }}
.data-row {{ display:flex; justify-content:space-between; align-items:baseline; padding:0.5rem 0; border-bottom:1px solid #f0f0f0; }}
.data-row:last-child {{ border-bottom:none; }}
.data-key {{ font-size:0.78rem; color:#666; }}
.data-val {{ font-size:0.85rem; font-weight:600; color:#1a1a1a; text-align:right; }}
.data-col {{ padding:0 1rem; }}
.data-col:first-child {{ padding-left:0; border-right:1px solid #f0f0f0; padding-right:1.25rem; }}

/* VENTES TABLE */
.ventes-table {{ width:100%; border-collapse:collapse; font-size:0.8rem; }}
.ventes-table th {{ background:#f5f5f5; padding:0.5rem 0.75rem; text-align:left; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.06em; color:#666; border-bottom:2px solid #e0e0e0; }}
.ventes-table td {{ padding:0.5rem 0.75rem; border-bottom:1px solid #f0f0f0; }}
.ventes-table tr:hover td {{ background:#fffbf0; }}
.prix-badge {{ background:#fffbf0; color:#B8860B; font-weight:700; padding:0.15rem 0.5rem; border-radius:4px; }}

/* DPE BADGES */
.dpe-badge {{ color:white; font-weight:700; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem; display:inline-block; margin-right:0.25rem; }}
.badge-ok {{ background:#2DC653; color:white; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem; font-weight:600; }}
.badge-warn {{ background:#F0A617; color:white; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem; font-weight:600; }}
.badge-danger {{ background:#D62E2E; color:white; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem; font-weight:600; }}

/* RISQUES */
.risque-item {{ display:flex; align-items:center; gap:0.75rem; padding:0.5rem 0; border-bottom:1px solid #f0f0f0; }}
.risque-item:last-child {{ border-bottom:none; }}
.risque-dot {{ width:8px; height:8px; border-radius:50%; background:#E07426; flex-shrink:0; }}

/* PLU */
.zone-badge {{ display:inline-block; padding:0.3rem 0.85rem; border-radius:20px; font-weight:700; font-size:0.85rem; }}
.zone-U {{ background:#d4edda; color:#1a7a37; }}
.zone-AU {{ background:#fff3cd; color:#856404; }}
.zone-A {{ background:#f8d7da; color:#721c24; }}
.zone-N {{ background:#e2e3e5; color:#383d41; }}
.zone-other {{ background:#f5f5f5; color:#333; }}

/* FOOTER */
.report-footer {{ margin-top:3rem; padding-top:1rem; border-top:1px solid #e0e0e0; font-size:0.72rem; color:#999; display:flex; justify-content:space-between; }}
.sources-list {{ font-size:0.72rem; color:#999; margin-top:0.5rem; }}

/* PRINT */
@media print {{
  body {{ background:white; }}
  .page {{ max-width:none; padding:1cm; box-shadow:none; }}
  .no-print {{ display:none; }}
  .section {{ page-break-inside:avoid; }}
  @page {{ margin:1cm; }}
}}
@media(max-width:700px) {{
  .exec-summary {{ grid-template-columns:1fr 1fr; }}
  .data-grid {{ grid-template-columns:1fr; }}
  .data-col:first-child {{ border-right:none; padding-right:0; border-bottom:1px solid #f0f0f0; padding-bottom:1rem; margin-bottom:1rem; }}
}}
</style>
</head>
<body>
<div class="page">

<!-- HEADER -->
<div class="report-header">
  <div>
    <div class="report-logo">Lex <span>Foncier</span></div>
    <div style="font-size:0.7rem;color:#999;margin-top:0.2rem">La donnée foncière fiable, instantanée, opposable</div>
  </div>
  <div class="report-meta">
    Rapport généré le {date_rapport}<br>
    Sources : BAN · IGN · DGFiP · GPU · Géorisques · ADEME<br>
    Durée d'analyse : {meta.get('temps_secondes', '—')}s
  </div>
</div>

<!-- TITRE -->
<div class="report-title">
  <h1>{meta.get('address_normalized', meta.get('address_input',''))}</h1>
  <div class="subtitle">
    {meta.get('commune','')} · {meta.get('code_postal','')} · 
    Dép. {meta.get('departement','')} · 
    Code INSEE : {meta.get('code_insee','')}
  </div>
</div>

<!-- RÉSUMÉ EXÉCUTIF -->
<div class="exec-summary">
  <div class="exec-item">
    <span class="exec-val">{_fmt_m2(cadastre.get('surface_m2',0)).replace(' m²','')}</span>
    <span class="exec-label">m² parcelle</span>
  </div>
  <div class="exec-item">
    <span class="exec-val">{_fmt_price(stats.get('prix_m2_median',0)).replace(' €','') if stats.get('prix_m2_median') else '—'}</span>
    <span class="exec-label">€/m² médiane DVF</span>
  </div>
  <div class="exec-item">
    <span class="exec-val">{plu.get('zone_principale', plu.get('type_zone','—'))}</span>
    <span class="exec-label">Zone PLU</span>
  </div>
  <div class="exec-item">
    <span class="exec-val">{risks.get('nb_risques', 0)}</span>
    <span class="exec-label">Risque(s) identifié(s)</span>
  </div>
</div>

<!-- 1. IDENTIFICATION CADASTRALE -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">🗺️</span>
    <span class="section-title">1. Identification cadastrale</span>
    <span class="section-source">Source : IGN API Carto</span>
  </div>
  <div class="section-body">
    <div class="data-grid">
      <div class="data-col">
        <div class="data-row"><span class="data-key">Référence cadastrale</span><span class="data-val">{cadastre.get('reference', '—')}</span></div>
        <div class="data-row"><span class="data-key">Section</span><span class="data-val">{cadastre.get('section', '—')}</span></div>
        <div class="data-row"><span class="data-key">Numéro</span><span class="data-val">{cadastre.get('numero', '—')}</span></div>
        <div class="data-row"><span class="data-key">Surface parcelle</span><span class="data-val">{_fmt_m2(cadastre.get('surface_m2',0))}</span></div>
      </div>
      <div class="data-col">
        <div class="data-row"><span class="data-key">Commune</span><span class="data-val">{cadastre.get('commune', meta.get('commune','—'))}</span></div>
        <div class="data-row"><span class="data-key">Code département</span><span class="data-val">{cadastre.get('code_dep', '—')}</span></div>
        <div class="data-row"><span class="data-key">Code INSEE (Cadastre)</span><span class="data-val">{meta.get('code_insee_cadastre','—')}</span></div>
        <div class="data-row"><span class="data-key">Coordonnées</span><span class="data-val">{meta.get('coordinates',{}).get('lat',''):.5f}, {meta.get('coordinates',{}).get('lon',''):.5f}</span></div>
      </div>
    </div>
    {'<p style="margin-top:0.75rem;font-size:0.75rem;color:#e07426;"><b>⚠ Note :</b> ' + cadastre.get('erreur','') + '</p>' if cadastre.get('erreur') else ''}
  </div>
</div>

<!-- 2. URBANISME (PLU) -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">📐</span>
    <span class="section-title">2. Urbanisme & PLU</span>
    <span class="section-source">Source : Géoportail Urbanisme — IGN / DGALN</span>
  </div>
  <div class="section-body">
    <div style="margin-bottom:1rem">
      <span class="zone-badge zone-{plu.get('type_zone','other')[:2] if plu.get('type_zone') else 'other'}">{plu.get('zone_principale','—')}</span>
      <span style="margin-left:0.75rem;font-size:0.85rem;color:#333">{plu.get('constructibilite','—')}</span>
    </div>
    <div class="data-grid">
      <div class="data-col">
        <div class="data-row"><span class="data-key">Type de zone</span><span class="data-val">{plu.get('type_zone','—')}</span></div>
        <div class="data-row"><span class="data-key">Libellé long</span><span class="data-val" style="max-width:200px;text-align:right;font-size:0.78rem">{plu.get('libelle_long','—')[:60]}</span></div>
        <div class="data-row"><span class="data-key">Constructibilité</span><span class="data-val">{plu.get('constructibilite','—')}</span></div>
      </div>
      <div class="data-col">
        <div class="data-row"><span class="data-key">Type document</span><span class="data-val">{plu.get('document_urbanisme',{}).get('type','—')}</span></div>
        <div class="data-row"><span class="data-key">État</span><span class="data-val">{plu.get('document_urbanisme',{}).get('etat','—')}</span></div>
        <div class="data-row"><span class="data-key">Date approbation</span><span class="data-val">{plu.get('document_urbanisme',{}).get('date_approbation','—')}</span></div>
      </div>
    </div>
    <p style="margin-top:0.75rem;font-size:0.78rem;color:#666"><b>Détail :</b> {plu.get('constructibilite_detail','—')}</p>
    {f'<p style="margin-top:0.5rem"><a href="{plu.get("document_urbanisme",{}).get("lien_reglement","")}" style="font-size:0.78rem;color:#B8860B">↗ Accéder au règlement PDF</a></p>' if plu.get('document_urbanisme',{}).get('lien_reglement') else ''}
    {'<p style="margin-top:0.75rem;font-size:0.75rem;color:#e07426;"><b>⚠ Note :</b> ' + plu.get('erreur','') + '</p>' if plu.get('erreur') else ''}
  </div>
</div>


<!-- 3. TRANSACTIONS DVF -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">💶</span>
    <span class="section-title">3. Marché immobilier — Transactions DVF</span>
    <span class="section-source">Source : DGFiP / data.gouv.fr</span>
  </div>
  <div class="section-body">
    {"" if not dvf.get('erreur') else f'<p style="color:#e07426;margin-bottom:1rem"><b>⚠</b> {dvf.get("erreur")}</p>'}
    <div class="data-grid" style="margin-bottom:1.25rem">
      <div class="data-col">
        <div class="data-row"><span class="data-key">Prix médian au m²</span><span class="data-val" style="color:#B8860B;font-size:1rem">{_fmt_price(stats.get('prix_m2_median',0))}/m²</span></div>
        <div class="data-row"><span class="data-key">Prix moyen au m²</span><span class="data-val">{_fmt_price(stats.get('prix_m2_moyen',0))}/m²</span></div>
        <div class="data-row"><span class="data-key">Fourchette min</span><span class="data-val">{_fmt_price(stats.get('prix_m2_min',0))}/m²</span></div>
      </div>
      <div class="data-col">
        <div class="data-row"><span class="data-key">Fourchette max</span><span class="data-val">{_fmt_price(stats.get('prix_m2_max',0))}/m²</span></div>
        <div class="data-row"><span class="data-key">Transactions analysées</span><span class="data-val">{stats.get('nb_transactions',0)}</span></div>
        <div class="data-row"><span class="data-key">Rayon de recherche</span><span class="data-val">{dvf.get('rayon_m', dvf.get('radius_m', 500))} m</span></div>
      </div>
    </div>
    {"" if not ventes else f"""
    <table class="ventes-table">
      <thead><tr>
        <th>Date</th><th>Type de bien</th><th>Nature</th>
        <th>Surface bâti</th><th>Surface terrain</th>
        <th>Valeur</th><th>Prix/m²</th><th>Lots</th>
      </tr></thead>
      <tbody>
        {"".join([f'''<tr>
          <td>{v.get("date","—")}</td>
          <td>{v.get("type_bien","—")}</td>
          <td>{v.get("nature_mutation","—")}</td>
          <td>{_fmt_m2(v.get("surface_bati_m2",0))}</td>
          <td>{_fmt_m2(v.get("surface_terrain_m2",0))}</td>
          <td>{_fmt_price(v.get("valeur_euros",0))}</td>
          <td><span class="prix-badge">{_fmt_price(v.get("prix_m2",0))}</span></td>
          <td>{v.get("nb_lots",0)}</td>
        </tr>''' for v in ventes])}
      </tbody>
    </table>"""}
    <p style="margin-top:0.75rem;font-size:0.72rem;color:#999">Période : {stats.get('periode', 'Non disponible')} · Données certifiées DGFiP non manipulables</p>
  </div>
</div>

<!-- 4. GÉORISQUES -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">⚠️</span>
    <span class="section-title">4. Risques naturels & technologiques (ERP)</span>
    <span class="section-source">Source : Géorisques — BRGM / Ministère Transition Écologique</span>
  </div>
  <div class="section-body">
    <div style="margin-bottom:1rem">{_risque_badge(risks.get("nb_risques",0))}</div>
    {f"""<div>{"".join([f'''<div class="risque-item">
      <div class="risque-dot"></div>
      <div>
        <span style="font-weight:600;font-size:0.85rem">{r.get("libelle","—")}</span>
        <span style="color:#999;font-size:0.75rem;margin-left:0.5rem">Code {r.get("code_risque","")}</span>
      </div>
    </div>''' for r in risques_list])}</div>""" if risques_list else '<p style="color:#666;font-size:0.85rem">Aucun risque répertorié pour cette commune dans le rayon d'analyse.</p>'}
    
    {f"""<div style="margin-top:1rem;padding:0.75rem;background:#f9f9f9;border-radius:4px">
      <div style="font-size:0.78rem;font-weight:600;margin-bottom:0.5rem">Retrait-gonflement des argiles</div>
      <div style="font-size:0.82rem">Exposition : <b>{risks.get("argiles",{}).get("exposition","Non renseigné")}</b></div>
    </div>""" if risks.get("argiles") else ''}
    
    {f"""<div style="margin-top:0.75rem;padding:0.75rem;background:#eff8ff;border-left:3px solid #3b82f6;border-radius:0 4px 4px 0">
      <div style="font-size:0.78rem;font-weight:600;color:#1d4ed8;margin-bottom:0.25rem">Zone inondable</div>
      <div style="font-size:0.82rem">{risks.get("inondation",{}).get("nb_zones",0)} zone(s) identifiée(s) dans un rayon de 500m</div>
    </div>""" if risks.get("inondation",{}).get("present") else ''}
  </div>
</div>

<!-- 5. DPE -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">🏠</span>
    <span class="section-title">5. Performance énergétique (DPE)</span>
    <span class="section-source">Source : ADEME — Base nationale des DPE</span>
  </div>
  <div class="section-body">
    {f"""<p style="color:#666;font-size:0.85rem;margin-bottom:0.75rem">{dpe.get("nb_dpe_proches",0)} DPE disponible(s) dans un rayon de 200m</p>
    {"".join([f'''<div style="display:flex;align-items:center;gap:1rem;padding:0.6rem 0;border-bottom:1px solid #f0f0f0">
      {_dpe_badge(d.get("etiquette_dpe","?"))} 
      {_dpe_badge(d.get("etiquette_ges","?"))}
      <span style="font-size:0.8rem;color:#333">{d.get("type_batiment","—")} · {d.get("surface_m2",0) or "—"} m² · Construit en {d.get("annee_construction","?")}</span>
      <span style="margin-left:auto;font-size:0.75rem;color:#999">{d.get("date","")[:10] if d.get("date") else "—"}</span>
    </div>''' for d in dpe_proches])}""" if dpe_proches else '<p style="color:#666;font-size:0.85rem">Aucun DPE disponible dans un rayon de 200m. Consultez la base ADEME pour la commune.</p>'}
    {'<p style="margin-top:0.75rem;font-size:0.75rem;color:#e07426;"><b>⚠ Note :</b> ' + dpe.get('erreur','') + '</p>' if dpe.get('erreur') else ''}
  </div>
</div>

<!-- 6. ADRESSE COMPLÈTE -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">📍</span>
    <span class="section-title">6. Identification administrative</span>
    <span class="section-source">Source : Base Adresse Nationale (BAN)</span>
  </div>
  <div class="section-body">
    <div class="data-grid">
      <div class="data-col">
        <div class="data-row"><span class="data-key">Adresse normalisée BAN</span><span class="data-val">{adresse.get('adresse_complete', meta.get('address_normalized','—'))}</span></div>
        <div class="data-row"><span class="data-key">Commune</span><span class="data-val">{adresse.get('commune', meta.get('commune','—'))}</span></div>
        <div class="data-row"><span class="data-key">Code postal</span><span class="data-val">{adresse.get('code_postal', meta.get('code_postal','—'))}</span></div>
        <div class="data-row"><span class="data-key">Code INSEE</span><span class="data-val">{adresse.get('code_insee', meta.get('code_insee','—'))}</span></div>
      </div>
      <div class="data-col">
        <div class="data-row"><span class="data-key">Département</span><span class="data-val">{adresse.get('departement', meta.get('departement','—'))}</span></div>
        <div class="data-row"><span class="data-key">Région</span><span class="data-val">{adresse.get('region', meta.get('region','—'))}</span></div>
        <div class="data-row"><span class="data-key">Latitude</span><span class="data-val">{meta.get('coordinates',{}).get('lat','—')}</span></div>
        <div class="data-row"><span class="data-key">Longitude</span><span class="data-val">{meta.get('coordinates',{}).get('lon','—')}</span></div>
      </div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="no-print" style="text-align:center;margin:2rem 0 1rem">
  <button onclick="window.print()" style="background:#B8860B;color:white;border:none;padding:0.75rem 2.5rem;border-radius:6px;font-size:0.95rem;font-weight:600;cursor:pointer">🖨️ Imprimer / Exporter PDF</button>
  <p style="margin-top:0.5rem;font-size:0.75rem;color:#999">Ctrl+P → Enregistrer en PDF</p>
</div>

<div class="report-footer">
  <div>
    <b>Lex Foncier</b> — Rapport généré le {date_rapport}<br>
    Ce rapport est fourni à titre informatif à partir de données publiques officielles. Il ne constitue pas un avis juridique.
  </div>
  <div style="text-align:right">
    <b>Sources officielles :</b><br>
    BAN (DINUM) · IGN API Carto · DGFiP DVF · GPU DGALN<br>
    Géorisques (BRGM) · ADEME DPE · Licences Ouvertes Etalab
  </div>
</div>

</div>
</body>
</html>"""
    return html
