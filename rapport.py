"""
rapport.py — Rapport foncier HTML professionnel imprimable
Lex Foncier v2.0
"""
from datetime import datetime

DPE_COLORS = {"A":"#2DC653","B":"#79CC41","C":"#CADD28","D":"#FFEE08","E":"#F0A617","F":"#E07426","G":"#D62E2E"}

def _fmt_price(v):
    if not v or v == 0: return "—"
    return "{:,.0f} €".format(v).replace(",", " ")

def _fmt_m2(v):
    if not v or v == 0: return "—"
    return "{:,.0f} m²".format(v).replace(",", " ")

def _dpe_badge(label):
    c = DPE_COLORS.get(label, "#999")
    return '<span style="background:' + c + ';color:white;padding:0.15rem 0.5rem;border-radius:4px;font-weight:700;font-size:0.8rem">' + str(label) + '</span>'

def _zone_badge(typezone, label):
    if typezone.startswith("U"): bg, fg = "#d4edda", "#1a7a37"
    elif typezone.startswith("AU"): bg, fg = "#fff3cd", "#856404"
    elif typezone.startswith("A"): bg, fg = "#f8d7da", "#721c24"
    elif typezone.startswith("N"): bg, fg = "#e2e3e5", "#383d41"
    else: bg, fg = "#f5f5f5", "#333"
    return '<span style="background:' + bg + ';color:' + fg + ';padding:0.3rem 0.85rem;border-radius:20px;font-weight:700;font-size:0.85rem">' + str(label) + '</span>'

def _risque_badge(count):
    if count == 0:
        return '<span style="background:#d4edda;color:#1a7a37;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.82rem;font-weight:600">✓ Aucun risque identifié</span>'
    if count <= 2:
        return '<span style="background:#fff3cd;color:#856404;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.82rem;font-weight:600">' + str(count) + ' risque(s) identifié(s)</span>'
    return '<span style="background:#f8d7da;color:#721c24;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.82rem;font-weight:600">' + str(count) + ' risques identifiés</span>'

def _row(key, val):
    return '<div class="dr"><span>' + str(key) + '</span><b>' + str(val) + '</b></div>'

def _section(icon, title, source, body):
    return (
        '<div class="sec">'
        '<div class="sec-hd"><span>' + icon + '</span><span class="sec-ttl">' + title + '</span>'
        '<span class="sec-src">' + source + '</span></div>'
        '<div class="sec-bd">' + body + '</div></div>'
    )

CSS = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1a1a1a; background: #f5f5f0; }
.page { max-width: 920px; margin: 0 auto; background: white; padding: 2.5rem; }
.rh { display:flex; justify-content:space-between; align-items:flex-start; padding-bottom:1.5rem; border-bottom:3px solid #B8860B; margin-bottom:1.75rem; }
.rl { font-size:1.35rem; font-weight:700; color:#B8860B; }
.rl span { color:#1a1a1a; }
.rm { text-align:right; font-size:0.75rem; color:#888; line-height:1.9; }
.rt h1 { font-size:1.45rem; font-weight:700; margin-bottom:0.3rem; }
.rt .sub { font-size:0.82rem; color:#666; margin-bottom:1.5rem; }
.exec { display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; background:#fffbf0; border:2px solid #B8860B; border-radius:8px; padding:1.25rem; margin-bottom:2rem; }
.ex-it { text-align:center; }
.ex-val { font-size:1.55rem; font-weight:700; color:#B8860B; display:block; line-height:1; margin-bottom:0.2rem; }
.ex-lbl { font-size:0.67rem; text-transform:uppercase; letter-spacing:0.07em; color:#888; }
.sec { margin-bottom:1.75rem; }
.sec-hd { display:flex; align-items:center; gap:0.6rem; padding:0.6rem 1rem; background:#1a1a1a; color:white; border-radius:6px 6px 0 0; }
.sec-ttl { font-size:0.82rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; }
.sec-src { margin-left:auto; font-size:0.62rem; color:rgba(255,255,255,0.55); }
.sec-bd { border:1px solid #e0e0e0; border-top:none; border-radius:0 0 6px 6px; padding:1.25rem; }
.g2 { display:grid; grid-template-columns:1fr 1fr; gap:0; }
.gc { padding:0 1rem; }
.gc:first-child { padding-left:0; border-right:1px solid #f0f0f0; padding-right:1.25rem; }
.dr { display:flex; justify-content:space-between; align-items:baseline; padding:0.45rem 0; border-bottom:1px solid #f5f5f5; font-size:0.8rem; }
.dr:last-child { border-bottom:none; }
.dr span { color:#777; }
.dr b { font-weight:600; text-align:right; max-width:55%; word-break:break-word; }
.vt { width:100%; border-collapse:collapse; font-size:0.78rem; margin-top:0.75rem; }
.vt th { background:#f5f5f5; padding:0.4rem 0.6rem; text-align:left; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.06em; color:#888; border-bottom:2px solid #e0e0e0; }
.vt td { padding:0.4rem 0.6rem; border-bottom:1px solid #f5f5f5; }
.vt tr:last-child td { border-bottom:none; }
.pb { color:#B8860B; font-weight:700; }
.rq { display:flex; align-items:center; gap:0.6rem; padding:0.35rem 0; border-bottom:1px solid #f5f5f5; font-size:0.82rem; }
.rq:last-child { border-bottom:none; }
.rd { width:7px; height:7px; border-radius:50%; background:#E07426; flex-shrink:0; }
.dpe-row { display:flex; align-items:center; gap:0.5rem; padding:0.4rem 0; border-bottom:1px solid #f5f5f5; font-size:0.8rem; }
.dpe-row:last-child { border-bottom:none; }
.stats-box { display:grid; grid-template-columns:2fr 1fr 1fr 1fr; gap:0.75rem; margin-bottom:1rem; }
.s-main { background:#fffbf0; border:1px solid rgba(184,134,11,0.25); border-radius:6px; padding:0.75rem; text-align:center; }
.s-main .v { font-size:1.35rem; font-weight:700; color:#B8860B; display:block; line-height:1; }
.s-main .u { font-size:0.75rem; color:#B8860B; }
.s-main .l { font-size:0.62rem; color:#888; text-transform:uppercase; letter-spacing:0.06em; display:block; margin-top:0.2rem; }
.s-item { background:#f9f9f9; border:1px solid #e8e8e8; border-radius:6px; padding:0.5rem 0.75rem; }
.s-item .sl { font-size:0.68rem; color:#888; text-transform:uppercase; letter-spacing:0.06em; display:block; margin-bottom:0.15rem; }
.s-item .sv { font-weight:700; font-size:0.82rem; }
.argile-box { margin-top:0.75rem; padding:0.75rem; background:#f9f9f9; border-radius:4px; font-size:0.82rem; }
.flood-box { margin-top:0.75rem; padding:0.75rem; background:#eff8ff; border-left:3px solid #3b82f6; border-radius:0 4px 4px 0; font-size:0.82rem; }
.footer-rf { margin-top:2.5rem; padding-top:1rem; border-top:1px solid #e0e0e0; font-size:0.7rem; color:#aaa; display:flex; justify-content:space-between; gap:2rem; }
.print-btn { display:block; text-align:center; margin:2rem 0 1rem; }
.print-btn button { background:#B8860B; color:white; border:none; padding:0.75rem 2.5rem; border-radius:6px; font-size:0.95rem; font-weight:600; cursor:pointer; }
.warn { color:#e07426; font-size:0.75rem; margin-top:0.5rem; }
.link-gold { color:#B8860B; font-size:0.78rem; display:inline-block; margin-top:0.5rem; }
.note { font-size:0.72rem; color:#aaa; margin-top:0.75rem; }
@media print {
  body { background:white; }
  .page { max-width:none; padding:1cm; box-shadow:none; }
  .print-btn { display:none; }
  .sec { page-break-inside:avoid; }
  @page { margin:1cm; }
}
@media(max-width:700px){.exec{grid-template-columns:1fr 1fr}.g2{grid-template-columns:1fr}.gc:first-child{border-right:none;padding-right:0;border-bottom:1px solid #f0f0f0;padding-bottom:1rem;margin-bottom:1rem}.stats-box{grid-template-columns:1fr 1fr}}"""

def generate_rapport(data: dict) -> str:
    meta  = data.get("meta", {})
    cad   = data.get("cadastre", {})
    dvf   = data.get("dvf", {})
    plu   = data.get("plu", {})
    risks = data.get("risks", {})
    dpe   = data.get("dpe", {})
    adr   = data.get("adresse", {})
    stats = dvf.get("stats", {})
    ventes= (dvf.get("ventes_logements") or dvf.get("ventes") or [])[:12]
    risques = risks.get("risques_gaspar", [])
    dpes  = (dpe.get("dpe_adresse") or [])[:6]
    coords = meta.get("coordinates", {})
    doc_urba = plu.get("document_urbanisme", {})
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    # ── Résumé exécutif ──
    prix_med = stats.get("prix_m2_median", 0)
    exec_html = (
        '<div class="ex-it"><span class="ex-val">' + (_fmt_m2(cad.get("surface_m2",0)).replace(" m²","") if cad.get("surface_m2") else "—") + '</span><span class="ex-lbl">m² parcelle</span></div>'
        '<div class="ex-it"><span class="ex-val">' + (_fmt_price(prix_med).replace(" €","") if prix_med else "—") + '</span><span class="ex-lbl">€/m² médiane DVF</span></div>'
        '<div class="ex-it"><span class="ex-val">' + (plu.get("zone_principale") or plu.get("type_zone") or "—") + '</span><span class="ex-lbl">Zone PLU</span></div>'
        '<div class="ex-it"><span class="ex-val">' + str(risks.get("nb_risques", 0)) + '</span><span class="ex-lbl">Risque(s)</span></div>'
    )

    # ── Section 1 : Cadastre ──
    cad_body = ""
    if cad.get("erreur"):
        cad_body = '<p class="warn">⚠ ' + cad["erreur"] + '</p>'
    else:
        cad_body = (
            '<div class="g2">'
            '<div class="gc">'
            + _row("Référence cadastrale", cad.get("reference","—"))
            + _row("Section", cad.get("section","—"))
            + _row("Numéro", cad.get("numero","—"))
            + _row("Surface parcelle", _fmt_m2(cad.get("surface_m2",0)))
            + '</div><div class="gc">'
            + _row("Commune", cad.get("commune", meta.get("commune","—")))
            + _row("Code département", cad.get("code_dep","—"))
            + _row("Code INSEE Cadastre", meta.get("code_insee_cadastre","—"))
            + _row("Coordonnées GPS", str(round(coords.get("lat",0),5)) + ", " + str(round(coords.get("lon",0),5)))
            + '</div></div>'
        )

    # ── Section 2 : PLU ──
    typez = plu.get("type_zone","")
    plu_body = ""
    if plu.get("erreur"):
        plu_body = '<p class="warn">⚠ ' + plu["erreur"] + '</p>'
    else:
        lien_reg = doc_urba.get("lien_reglement","")
        lien_html = ('<a href="' + lien_reg + '" target="_blank" class="link-gold">↗ Accéder au règlement PDF</a>') if lien_reg else ""
        plu_body = (
            '<div style="margin-bottom:1rem">'
            + _zone_badge(typez, plu.get("zone_principale") or typez or "—")
            + ' <span style="margin-left:0.5rem;font-size:0.85rem">' + (plu.get("constructibilite") or "—") + '</span>'
            + '</div>'
            '<div class="g2">'
            '<div class="gc">'
            + _row("Type de zone", typez or "—")
            + _row("Libellé complet", (plu.get("libelle_long") or "—")[:70])
            + _row("Constructibilité", plu.get("constructibilite","—"))
            + '</div><div class="gc">'
            + _row("Type document", doc_urba.get("type","—"))
            + _row("État", doc_urba.get("etat","—"))
            + _row("Date approbation", doc_urba.get("date_approbation","—"))
            + _row("ID Urbanisme", doc_urba.get("id_urbanisme","—")[:30])
            + '</div></div>'
            '<p style="margin-top:0.75rem;font-size:0.8rem;color:#555"><b>Détail :</b> ' + (plu.get("constructibilite_detail") or "—") + '</p>'
            + lien_html
        )

    # ── Section 3 : DVF ──
    dvf_body = ""
    if dvf.get("erreur"):
        dvf_body = '<p class="warn">⚠ ' + dvf["erreur"] + '</p>'
    elif not stats:
        dvf_body = '<p style="color:#888;font-size:0.85rem;font-style:italic">Aucune transaction DVF trouvée dans ce rayon. Essayez une adresse plus centrale ou augmentez le rayon.</p>'
    else:
        stats_html = (
            '<div class="stats-box">'
            '<div class="s-main"><span class="v">' + _fmt_price(stats.get("prix_m2_median",0)).replace(" €","") + '</span><span class="u">€/m²</span><span class="l">Prix médian</span></div>'
            '<div class="s-item"><span class="sl">Prix moyen</span><span class="sv">' + _fmt_price(stats.get("prix_m2_moyen",0)) + '/m²</span></div>'
            '<div class="s-item"><span class="sl">Min / Max</span><span class="sv">' + _fmt_price(stats.get("prix_m2_min",0)) + ' – ' + _fmt_price(stats.get("prix_m2_max",0)) + '</span></div>'
            '<div class="s-item"><span class="sl">Transactions</span><span class="sv">' + str(stats.get("nb_transactions",0)) + ' ventes</span></div>'
            '</div>'
        )
        ventes_rows = ""
        for v in ventes:
            surf = v.get("surface_bati_m2") or v.get("surface_terrain_m2") or 0
            ventes_rows += (
                "<tr>"
                "<td>" + str(v.get("date","—"))[:10] + "</td>"
                "<td>" + str(v.get("type_bien","—"))[:30] + "</td>"
                "<td>" + str(v.get("nature_mutation","—"))[:25] + "</td>"
                "<td>" + _fmt_m2(surf) + "</td>"
                "<td>" + _fmt_price(v.get("valeur_euros",0)) + "</td>"
                "<td><b class='pb'>" + _fmt_price(v.get("prix_m2",0)) + "</b></td>"
                "<td>" + str(v.get("nb_lots",0) or "—") + "</td>"
                "</tr>"
            )
        table_html = (
            '<table class="vt"><thead><tr>'
            '<th>Date</th><th>Type de bien</th><th>Nature</th>'
            '<th>Surface</th><th>Valeur</th><th>€/m²</th><th>Lots</th>'
            '</tr></thead><tbody>' + ventes_rows + '</tbody></table>'
        ) if ventes_rows else ""
        dvf_body = stats_html + table_html + '<p class="note">Période : ' + stats.get("periode","—") + ' · Données certifiées DGFiP · Rayon ' + str(dvf.get("rayon_m", dvf.get("radius_m",500))) + 'm</p>'

    # ── Section 4 : Géorisques ──
    risques_html = _risque_badge(risks.get("nb_risques",0)) + '<div style="margin-top:0.75rem">'
    if risques:
        for rq in risques:
            risques_html += '<div class="rq"><div class="rd"></div><span><b>' + (rq.get("libelle") or rq.get("code_risque") or "—") + '</b></span><span style="color:#888;font-size:0.75rem;margin-left:auto">Code ' + str(rq.get("code_risque","")) + '</span></div>'
    else:
        risques_html += '<p style="color:#888;font-size:0.82rem;margin-top:0.5rem">Aucun risque répertorié pour cette commune.</p>'
    risques_html += '</div>'
    argiles = risks.get("argiles",{})
    if argiles.get("exposition"):
        risques_html += '<div class="argile-box"><b>Retrait-gonflement des argiles :</b> ' + argiles["exposition"] + '</div>'
    inond = risks.get("inondation",{})
    if inond.get("present"):
        risques_html += '<div class="flood-box"><b style="color:#1d4ed8">Zone inondable identifiée</b><br>' + str(inond.get("nb_zones",0)) + ' zone(s) dans un rayon de 500m</div>'

    # ── Section 5 : DPE ──
    dpe_body = ""
    if dpe.get("erreur"):
        dpe_body = '<p class="warn">⚠ ' + dpe["erreur"] + '</p>'
    elif dpes:
        dpe_body = '<p style="font-size:0.78rem;color:#888;margin-bottom:0.75rem">' + str(dpe.get("nb_dpe_proches",len(dpes))) + ' DPE disponible(s) dans un rayon de 200m</p>'
        for dp in dpes:
            dpe_body += (
                '<div class="dpe-row">'
                + _dpe_badge(dp.get("etiquette_dpe","?"))
                + _dpe_badge(dp.get("etiquette_ges","?"))
                + '<span style="font-size:0.8rem;color:#333;margin-left:0.25rem">'
                + str(dp.get("type_batiment","—")) + " · "
                + str(dp.get("surface_m2") or "—") + " m² · "
                + "Construit " + str(dp.get("annee_construction","?"))
                + "</span>"
                + '<span style="margin-left:auto;font-size:0.72rem;color:#aaa">' + str(dp.get("date",""))[:10] + "</span>"
                + "</div>"
            )
    else:
        dpe_body = '<p style="color:#888;font-size:0.85rem;font-style:italic">Aucun DPE disponible dans un rayon de 200m. Consultez directement la base ADEME pour la commune.</p>'

    # ── Section 6 : Adresse ──
    adr_body = (
        '<div class="g2">'
        '<div class="gc">'
        + _row("Adresse normalisée BAN", adr.get("adresse_complete", meta.get("address_normalized","—")))
        + _row("Commune", adr.get("commune", meta.get("commune","—")))
        + _row("Code postal", adr.get("code_postal", meta.get("code_postal","—")))
        + _row("Code INSEE", adr.get("code_insee", meta.get("code_insee","—")))
        + '</div><div class="gc">'
        + _row("Département", adr.get("departement", meta.get("departement","—")))
        + _row("Région", adr.get("region", meta.get("region","—")))
        + _row("Latitude", str(coords.get("lat","—")))
        + _row("Longitude", str(coords.get("lon","—")))
        + '</div></div>'
    )

    # ── Assemblage ──
    sections = (
        _section("🗺️","1. Identification cadastrale","IGN API Carto", cad_body)
        + _section("📐","2. Urbanisme & PLU","Géoportail Urbanisme — IGN / DGALN", plu_body)
        + _section("💶","3. Marché immobilier — Transactions DVF","DGFiP / data.gouv.fr", dvf_body)
        + _section("⚠️","4. Risques naturels & technologiques (ERP)","Géorisques — BRGM", risques_html)
        + _section("🏠","5. Performance énergétique (DPE)","ADEME — Base nationale des DPE", dpe_body)
        + _section("📍","6. Identification administrative","Base Adresse Nationale (BAN)", adr_body)
    )

    html = """<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rapport Foncier — """ + meta.get("address_normalized", meta.get("address_input","")) + """</title>
<style>""" + CSS + """</style>
</head><body><div class="page">

<div class="rh">
  <div>
    <div class="rl">Lex <span>Foncier</span></div>
    <div style="font-size:0.7rem;color:#aaa;margin-top:0.15rem">La donnée foncière fiable, instantanée, opposable</div>
  </div>
  <div class="rm">
    Rapport généré le """ + now + """<br>
    Sources : BAN · IGN · DGFiP · GPU · Géorisques · ADEME<br>
    Durée d'analyse : """ + str(meta.get("temps_secondes","—")) + """s · Géocodage : """ + str(round(meta.get("geocoding_score",0)*100)) + """%
  </div>
</div>

<div class="rt">
  <h1>""" + (meta.get("address_normalized") or meta.get("address_input","")) + """</h1>
  <div class="sub">""" + meta.get("commune","") + " · " + meta.get("code_postal","") + " · Dép. " + meta.get("departement","") + " · Code INSEE : " + meta.get("code_insee","") + """</div>
</div>

<div class="exec">""" + exec_html + """</div>

""" + sections + """

<div class="print-btn no-print">
  <button onclick="window.print()">🖨️ Imprimer / Exporter PDF</button>
  <p style="margin-top:0.4rem;font-size:0.73rem;color:#aaa">Ctrl+P puis "Enregistrer en PDF"</p>
</div>

<div class="footer-rf">
  <div><b>Lex Foncier</b> — Rapport généré le """ + now + """<br>
  Ce rapport est fourni à titre informatif à partir de données publiques officielles.<br>
  Il ne constitue pas un avis juridique ou immobilier.</div>
  <div style="text-align:right"><b>Sources officielles (Licences Ouvertes Etalab) :</b><br>
  BAN (DINUM) · IGN API Carto · DGFiP DVF<br>GPU DGALN · Géorisques (BRGM) · ADEME DPE</div>
</div>

</div></body></html>"""
    return html
