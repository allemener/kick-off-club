#!/usr/bin/env python3
"""Construit le site Brief & Rebrief à partir du dossier briefs/.

Usage :
    python3 build.py            # construit le site dans _site/
    python3 build.py --tout     # affiche aussi ce qui est programmé plus tard
                                # (briefs et debriefs)

Chaque sous-dossier de briefs/ est un brief. Voir GUIDE.md pour le format.
"""

import datetime as dt
import hashlib
import html
import re
import shutil
import sys
import zipfile
from pathlib import Path

import markdown
import pymupdf
from PIL import Image

RACINE = Path(__file__).parent
BRIEFS = RACINE / "briefs"
STATIQUE = RACINE / "statique"
PAGES = RACINE / "pages"
SORTIE = RACINE / "_site"

NOM_SITE = "Brief & Rebrief"
DESCRIPTION = "Un brief d'agence fictif chaque semaine, avec tout le dossier client. À toi de trier."

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

TYPES_DOC = {
    "message": "Message",
    "teams": "Réunion Teams",
    "compte-rendu": "Compte rendu",
    "mail": "E-mail",
    "note": "Note",
    "conversation": "Message Teams",
    "debrief": "Debrief du DC",
    "rendu": "Consignes de rendu",
    "rendus": "Rendus",
}

IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
LARGEUR_APERCU = 480


# --------------------------------------------------------------------------
# Lecture des fichiers
# --------------------------------------------------------------------------

def lire_markdown(chemin):
    """Sépare l'en-tête (entre deux lignes ---) du texte Markdown."""
    texte = chemin.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", texte, re.S)
    if m:
        for ligne in m.group(1).splitlines():
            if ":" in ligne and not ligne.lstrip().startswith("#"):
                cle, valeur = ligne.split(":", 1)
                valeur = valeur.strip()
                if len(valeur) > 1 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
                    valeur = valeur[1:-1]
                meta[cle.strip().lower()] = valeur
        texte = m.group(2)
    return meta, texte


def md_en_html(texte):
    rendu = markdown.markdown(texte, extensions=["tables", "sane_lists", "attr_list", "nl2br"])
    # Cases à cocher des tâches : « - [ ] » et « - [x] »
    rendu = rendu.replace("<li>[ ] ", '<li class="tache"><span aria-hidden="true">☐</span> ')
    return rendu.replace("<li>[x] ", '<li class="tache"><span aria-hidden="true">☑</span> ')


def lire_date(valeur):
    try:
        return dt.date.fromisoformat(valeur.strip())
    except (AttributeError, ValueError):
        return None


def date_fr(d, jour=False):
    if not d:
        return ""
    texte = f"{d.day} {MOIS[d.month - 1]} {d.year}"
    return f"{JOURS[d.weekday()]} {texte}" if jour else texte


def taille_lisible(octets):
    if octets < 1024:
        return f"{octets} o"
    if octets < 1024 ** 2:
        return f"{octets / 1024:.0f} Ko".replace(".", ",")
    return f"{octets / 1024 ** 2:.1f} Mo".replace(".", ",")


def e(texte):
    return html.escape(str(texte or ""), quote=True)


def nom_page(stem):
    return re.sub(r"[^a-z0-9-]", "-", stem.lower())


def charger_brief(dossier, aujourd_hui, montrer_tout):
    fiche = dossier / "brief.md"
    if not fiche.exists():
        print(f"  ! {dossier.name} ignoré : pas de fichier brief.md")
        return None
    meta, intro = lire_markdown(fiche)
    publication = lire_date(meta.get("publication", ""))
    brief = {
        "slug": dossier.name,
        "dossier": dossier,
        "titre": meta.get("titre", dossier.name),
        "client": meta.get("client", ""),
        "secteur": meta.get("secteur", ""),
        "livrable": meta.get("livrable", ""),
        "agence": meta.get("agence", ""),
        "publication": publication,
        "intro": intro.strip(),
        "accroche": meta.get("accroche", ""),
        "message": None,
        "documents": [],
        "debrief": None,
        "rendu": None,
        "date_debrief": None,
        "ressources": [],
    }
    for chemin in sorted(dossier.glob("*.md")):
        if chemin.name == "brief.md":
            continue
        dmeta, dtexte = lire_markdown(chemin)
        doc = {
            "nom": nom_page(chemin.stem),
            "source": chemin.stem,
            "meta": dmeta,
            "type": dmeta.get("type", "note"),
            "titre": dmeta.get("titre", chemin.stem),
            "texte": dtexte,
        }
        if chemin.name == "debrief.md":
            doc["type"] = "debrief"
            doc["nom"] = "debrief"
            # Par défaut, le debrief sort le lundi suivant la publication.
            date = lire_date(dmeta.get("publication", "")) or (publication + dt.timedelta(days=7) if publication else None)
            brief["date_debrief"] = date
            if date and (date <= aujourd_hui or montrer_tout):
                brief["debrief"] = doc
        elif chemin.name == "rendu.md":
            doc["type"] = "rendu"
            doc["nom"] = "rendu"
            brief["rendu"] = doc
        elif doc["type"] == "message" and brief["message"] is None:
            brief["message"] = doc
        else:
            brief["documents"].append(doc)
    ress = dossier / "ressources"
    if ress.is_dir():
        for f in sorted(ress.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                brief["ressources"].append(f)
    brief["rendus"] = charger_rendus(dossier / "rendus")
    brief["zip"] = f"Dossier_{brief['slug']}.zip"
    return brief


def charger_rendus(dossier):
    """Un sous-dossier par designer : ses visuels (dans l'ordre des noms) et credits.md."""
    rendus = []
    if not dossier.is_dir():
        return rendus
    for d in sorted(p for p in dossier.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        images = sorted((f for f in d.iterdir() if f.suffix.lower() in IMAGES), key=lambda f: f.name.lower())
        if not images:
            continue
        meta, texte = lire_markdown(d / "credits.md") if (d / "credits.md").exists() else ({}, "")
        rendus.append({"slug": d.name, "dossier": d, "images": images, "meta": meta, "texte": texte.strip(),
                       "nom": meta.get("nom", d.name)})
    return rendus


# --------------------------------------------------------------------------
# Liens entre les pièces
# --------------------------------------------------------------------------

def corriger_liens(contenu_html, b, base):
    """Transforme [texte](02-compte-rendu) en lien vers la bonne page.

    Noms reconnus : le nom d'un fichier .md du brief (sans .md), « ressources »
    pour le dossier client, « ressources.zip » pour le zip.
    """
    cibles = {"ressources": "ressources.html", "ressources.zip": b["zip"]}
    for d in b["documents"]:
        cibles[d["source"]] = f"{d['nom']}.html"
        cibles[d["source"] + ".md"] = f"{d['nom']}.html"

    def remplacer(m):
        cible = html.unescape(m.group(1))
        if cible in cibles:
            suffixe = "" if cible.endswith(".zip") else "#haut"
            return f'href="{e(base + cibles[cible])}{suffixe}"'
        return m.group(0)

    return re.sub(r'href="([^"#:/][^":]*)"', remplacer, contenu_html)


def etapes(b):
    """Toutes les pages d'un brief, dans l'ordre de lecture : (fichier, libellé, type)."""
    liste = [("index.html", "Le message", "message")]
    # Libellés courts pour le sommaire : champ « court » de chaque pièce, sinon son titre.
    liste += [(f"{d['nom']}.html", d["meta"].get("court") or d["titre"], d["type"]) for d in b["documents"]]
    if b["ressources"]:
        liste.append(("ressources.html", "Le dossier client", "dossier"))
    if b["rendu"]:
        liste.append(("rendu.html", b["rendu"]["meta"].get("court") or "Le rendu", "rendu"))
    if b["debrief"]:
        liste.append(("debrief.html", "Le debrief du DC", "debrief"))
    return liste


# --------------------------------------------------------------------------
# Gabarits HTML
# --------------------------------------------------------------------------

def page(titre, contenu, racine="", description=DESCRIPTION, actif="", cote="", plein=False, cote_bas=False):
    titre_complet = f"{titre} · {NOM_SITE}" if titre != NOM_SITE else NOM_SITE

    def lien(href, texte, cle):
        courant = ' aria-current="page"' if cle == actif else ""
        return f'<li><a href="{racine}{href}"{courant}>{texte}</a></li>'

    if plein:
        corps = contenu
    elif cote:
        corps = f"""<div class="plein avec-cote{' cote-bas' if cote_bas else ''}">
{cote}
<div class="page">
{contenu}
</div>
</div>"""
    else:
        corps = f"""<div class="colonne page">
{contenu}
</div>"""

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titre_complet)}</title>
<meta name="description" content="{e(description)}">
<link rel="stylesheet" href="{racine}style.css">
<link rel="icon" href="{racine}favicon.svg" type="image/svg+xml">
</head>
<body id="haut">
<a class="evitement" href="#contenu">Aller au contenu</a>
<header class="bandeau">
  <div class="plein bandeau-int">
    <a class="logo" href="{racine}index.html">{e(NOM_SITE)}</a>
    <nav aria-label="Navigation principale">
      <ul>
        {lien("index.html", "Brief", "semaine")}
        {lien("rendus.html", "Rendus", "rendus")}
        {lien("archives.html", "Archives", "archives")}
        {lien("a-propos.html", "À propos", "a-propos")}
      </ul>
    </nav>
  </div>
</header>
<main id="contenu" tabindex="-1">
{corps}
</main>
<footer class="pied">
  <div class="plein pied-int">
    <p>{e(NOM_SITE)} · Clients, personnes et agences sont fictifs. Gratuit, sans compte, sans pisteur. · <a href="{racine}mentions-legales.html">Mentions légales</a></p>
  </div>
</footer>
</body>
</html>
"""


# Couleur de pastille par type de pièce et par type de fichier
COULEURS_TYPE = {
    "message": "bleu", "teams": "violet", "compte-rendu": "ambre", "mail": "vert",
    "note": "rose", "conversation": "rose", "dossier": "ciel", "debrief": "rouge", "rendu": "gris", "rendus": "vert",
}
COULEURS_FICHIER = {
    "PDF": "rouge", "JPG": "vert", "JPEG": "vert", "PNG": "vert", "WEBP": "vert", "GIF": "vert",
    "SVG": "violet", "XLSX": "ambre", "CSV": "ambre", "TXT": "gris", "DOCX": "bleu", "PPTX": "rose",
}
COULEURS_GROUPES = ["bleu", "rose", "vert", "ambre", "violet", "ciel"]


def pastille(texte, couleur="gris"):
    return f'<span class="pastille p-{couleur}">{e(texte)}</span>'


def pastille_type(type_):
    libelle = {"dossier": "Dossier partagé"}.get(type_, TYPES_DOC.get(type_, "Document"))
    return pastille(libelle, COULEURS_TYPE.get(type_, "gris"))


def proprietes(lignes):
    """Liste de propriétés façon Notion : libellé à gauche, valeur à droite."""
    lignes = [(a, v) for a, v in lignes if v]
    if not lignes:
        return ""
    return '<dl class="proprietes">' + "".join(
        f"<div><dt>{e(a)}</dt><dd>{v}</dd></div>" for a, v in lignes) + "</dl>"


def proprietes_document(doc):
    m = doc["meta"]
    t = doc["type"]
    lignes = [("Type", pastille_type(t))]
    if t == "teams":
        champs = (("date", "Date"), ("duree", "Durée"), ("organisateur", "Organisé par"))
    elif t == "mail":
        champs = (("de", "De"), ("a", "À"), ("cc", "Cc"), ("date", "Date"), ("pieces", "Pièces jointes"))
    elif t == "rendu":
        champs = (("date_limite", "À rendre avant le"), ("format", "Format"))
    elif m.get("canal"):
        champs = (("de", "De"), ("canal", "Canal"), ("date", "Date"))
    else:
        champs = (("auteur", "Rédigé par"), ("date", "Date"), ("version", "Version"))
    lignes += [(libelle, e(m[cle])) for cle, libelle in champs if m.get(cle)]
    if t == "teams" and m.get("participants"):
        orgas, items = [], []
        for p in (x.strip() for x in m["participants"].split(";")):
            if not p:
                continue
            nom, _, reste = p.partition("(")
            orga, _, detail = reste.rstrip(")").partition(",")
            orga = orga.strip()
            if orga and orga not in orgas:
                orgas.append(orga)
            couleur = COULEURS_GROUPES[orgas.index(orga) % len(COULEURS_GROUPES)] if orga else "gris"
            items.append(f'<li>{pastille(nom.strip(), couleur)} <span class="detail">{e(", ".join(x for x in (orga, detail.strip()) if x))}</span></li>')
        lignes.append(("Participants", f'<ul class="liste-participants">{"".join(items)}</ul>'))
    return proprietes(lignes)


def date_doc(doc):
    return doc["meta"].get("date", "").split(",")[0]


def barre_laterale(b, courant, base=""):
    """Sommaire du brief, toujours visible à côté des pièces."""
    items = []
    for fichier, libelle, type_ in etapes(b):
        courant_attr = ' aria-current="page"' if fichier == courant else ""
        couleur = COULEURS_TYPE.get(type_, "gris")
        items.append(f'<li><a href="{e(base + fichier)}#haut"{courant_attr}>'
                     f'<span class="point p-{couleur}" aria-hidden="true"></span>'
                     f'<span class="cote-titre">{e(libelle)}</span></a></li>')
    if not b["debrief"] and b["date_debrief"]:
        items.append(f'<li><span class="cote-attente"><span class="point p-gris" aria-hidden="true"></span><span class="cote-titre">Le debrief du DC</span>'
                     f'<span class="cote-type">Le {e(date_fr(b["date_debrief"], jour=True))}</span></span></li>')
    liste = f'<ol class="cote-liste" role="list">{"".join(items)}</ol>'
    return f"""<nav class="cote" aria-label="Pièces du brief">
  <details open>
    <summary><span class="cote-client">{e(b['client'])}</span><span class="cote-ouvrir">Pièces du brief</span></summary>
    {liste}
  </details>
</nav>"""


def suivant_precedent(b, courant):
    liste = etapes(b)
    i = next((k for k, (f, _, _) in enumerate(liste) if f == courant), None)
    if i is None:
        return ""
    liens = []
    if i > 0:
        f, libelle, _ = liste[i - 1]
        liens.append(f'<a class="precedent" href="{e(f)}#haut"><span class="pn-sens">← Précédent</span><span>{e(libelle)}</span></a>')
    if i < len(liste) - 1:
        f, libelle, _ = liste[i + 1]
        liens.append(f'<a class="suivant" href="{e(f)}#haut"><span class="pn-sens">Suivant →</span><span>{e(libelle)}</span></a>')
    return f'<nav class="pn" aria-label="Pièce précédente et suivante">{"".join(liens)}</nav>'


def liste_pieces(b, base):
    rangs = []
    for d in b["documents"]:
        rangs.append(f"""<li>
  <a class="rang" href="{e(base + d['nom'])}.html#haut">
    <span class="rang-type">{pastille_type(d['type'])}</span>
    <span class="rang-titre">{e(d['titre'])}</span>
    <span class="rang-info">{e(date_doc(d))}</span>
  </a>
</li>""")
    if b["ressources"]:
        rangs.append(f"""<li>
  <a class="rang" href="{e(base)}ressources.html#haut">
    <span class="rang-type">{pastille_type('dossier')}</span>
    <span class="rang-titre">Dossier envoyé par le client</span>
    <span class="rang-info">{len(b['ressources'])} fichiers</span>
  </a>
</li>""")
    if b["rendu"]:
        limite = b["rendu"]["meta"].get("date_limite", "")
        rangs.append(f"""<li>
  <a class="rang" href="{e(base)}rendu.html#haut">
    <span class="rang-type">{pastille_type('rendu')}</span>
    <span class="rang-titre">{e(b['rendu']['titre'])}</span>
    <span class="rang-info">{e(f"Avant le {limite}" if limite else "")}</span>
  </a>
</li>""")
    if b["debrief"]:
        rangs.append(f"""<li>
  <a class="rang" href="{e(base)}debrief.html#haut">
    <span class="rang-type">{pastille_type('debrief')}</span>
    <span class="rang-titre">Le debrief du directeur de création</span>
    <span class="rang-info">À lire après le brief</span>
  </a>
</li>""")
    elif b["date_debrief"]:
        rangs.append(f"""<li>
  <span class="rang rang-attente">
    <span class="rang-type">{pastille('Bientôt', 'gris')}</span>
    <span class="rang-titre">Le debrief du directeur de création</span>
    <span class="rang-info">{e(date_fr(b['date_debrief'], jour=True))}</span>
  </span>
</li>""")
    return f'<ul class="rangs">{"".join(rangs)}</ul>'


def titre_message(m):
    """« Le message de la cheffe de projet », « Le message du chef de projet »…"""
    role = m.get("role", "").strip()
    if not role:
        return "Le message"
    if role.lower().startswith("le "):
        return "Le message du " + role[3:]
    if role.lower().startswith("les "):
        return "Le message des " + role[4:]
    return "Le message de " + role


def rendre_message(b, racine, base, accueil):
    """La page d'entrée d'un brief : le message, puis les pièces."""
    msg = b["message"]
    m = msg["meta"] if msg else {}
    date_pub = date_fr(b["publication"])
    fil = (f'<p class="fil">Brief de la semaine du {date_pub}</p>' if accueil
           else f'<p class="fil"><a href="{racine}archives.html">Archives</a> / {date_pub}</p>')

    recu = " · ".join(x for x in (m.get("date", ""), m.get("canal", "")) if x)
    props = proprietes([
        ("Demandé par", e(m.get("de", ""))),
        ("Client", e(b["client"])),
        ("Secteur", pastille(b["secteur"], "ambre") if b["secteur"] else ""),
        ("Projet", pastille(b["livrable"].split("(")[0].strip(), "bleu")),
        ("Reçu", e(recu)),
    ])

    bloc_message = ""
    if msg:
        corps = corriger_liens(md_en_html(msg["texte"]), b, base)
        auteur = m.get("de", "").split("(")[0].strip()
        bloc_message = f"""<section aria-labelledby="t-message">
  <h2 id="t-message">{e(titre_message(m))}</h2>
  <div class="message">
    <span class="avatar" aria-hidden="true">{e(auteur[:1].upper() or "?")}</span>
    <div class="message-corps prose">
{corps}
    </div>
  </div>
</section>"""

    gauche = f"""<div class="titre-brief">
{fil}
<h1>{e(b['titre'])}</h1>
<p class="chapeau">{e(b['intro'])}</p>
</div>"""
    contenu = f"""{props}
{bloc_message}
<section aria-labelledby="t-pieces">
  <h2 id="t-pieces">Pièces du dossier</h2>
  {liste_pieces(b, base)}
</section>"""
    titre = "Brief de la semaine" if accueil else b["titre"]
    return page(titre, contenu, racine=racine, actif="semaine" if accueil else "archives",
                description=f"Brief : {b['titre']}.", cote=gauche)


REPONSES = ["Carrément, envoie !", "Je suis chaud·e 🔥", "Motivé·e, je prends !"]


def rendre_invitation(b):
    """Page d'accueil : le ou la chef·fe de projet propose le projet, on répond pour entrer dans le brief."""
    m = b["message"]["meta"] if b["message"] else {}
    auteur = m.get("de", "").split("(")[0].strip() or "Ta cheffe de projet"
    poste = m.get("de", "").partition("(")[2].rstrip(")")
    accroche = b["accroche"] or (
        f"Hello ! On vient de signer un nouveau client : {b['client']}. "
        f"C'est pour un projet d'{b['livrable'].split('(')[0].strip().lower()}. Tu es dispo pour le prendre ?")
    cible = f"brief/{b['slug']}/index.html#haut"
    puces = "".join(f'<li><a class="puce" href="{e(cible)}">{e(r)}</a></li>' for r in REPONSES)
    contenu = f"""<div class="plein accueil">
<div class="chat" aria-labelledby="t-chat">
  <h1 class="fil" id="t-chat">Brief de la semaine du {date_fr(b['publication'])}<span class="visuellement-cache">, nouveau message de {e(auteur)}</span></h1>
  <div class="chat-tete">
    <span class="avatar" aria-hidden="true">{e(auteur[:1].upper())}</span>
    <div>
      <p class="chat-nom">{e(auteur)}</p>
      <p class="chat-poste">{e(poste)}</p>
    </div>
  </div>
  <div class="chat-fil">
    <p class="chat-heure">{e(m.get("date", "").split(",")[-1].strip() or "09:02")}</p>
    <p class="bulle">{e(accroche)}</p>
  </div>
  <div class="chat-reponse">
    <p class="etiquette-reponse" id="t-reponse">Réponds pour recevoir le brief</p>
    <ul class="puces" role="list" aria-labelledby="t-reponse">{puces}</ul>
  </div>
</div>
</div>"""
    return page("Brief de la semaine", contenu, actif="semaine", plein=True,
                description=f"Nouveau brief : {b['titre']}.")


def couleurs_participants(doc):
    """{nom: couleur}, une couleur par organisation, comme les pastilles des participants."""
    orgas, couleurs = [], {}
    for p in (x.strip() for x in doc["meta"].get("participants", "").split(";")):
        if not p:
            continue
        nom, _, reste = p.partition("(")
        orga = reste.rstrip(")").partition(",")[0].strip()
        if orga and orga not in orgas:
            orgas.append(orga)
        couleurs[nom.strip()] = COULEURS_GROUPES[orgas.index(orga) % len(COULEURS_GROUPES)] if orga else "gris"
    return couleurs


def aerer(corps):
    """Récap et compte rendu : « **Libellé** : texte » devient un libellé posé au-dessus du texte."""
    corps = re.sub(r"<li><strong>([^<]+)</strong> ?: (.)",
                   lambda m: f'<li class="cle"><span class="cle-titre">{m.group(1)}</span>{m.group(2).upper()}', corps)

    def entete(m):
        lignes = [l.strip() for l in m.group(1).split("<br />")]
        paires = [re.fullmatch(r"<strong>([^<]+)</strong> ?: (.+)", l, re.S) for l in lignes]
        if not all(paires):
            return m.group(0)
        return ('<dl class="entete">' + "".join(
            f"<div><dt>{x.group(1)}</dt><dd>{x.group(2)}</dd></div>" for x in paires) + "</dl>")
    return re.sub(r"<p>(<strong>.*?)</p>", entete, corps, flags=re.S)


def entete_mail(m):
    """En-tête façon messagerie : expéditeur, destinataires, date, pièce jointe."""
    nom, _, adresse = m.get("de", "").partition("<")
    nom = nom.strip()
    adresse = f' <span class="mail-adresse">&lt;{e(adresse.rstrip(">").strip())}&gt;</span>' if adresse else ""
    dest = [f"<p><span class=\"mail-lib\">{lib}</span> {e(re.sub(r' *<[^>]*>', '', m[cle]).replace(";", ","))}</p>"
            for cle, lib in (("a", "À"), ("cc", "Cc")) if m.get(cle)]
    pj = ""
    if m.get("pieces"):
        fichier, _, note = m["pieces"].partition("(")
        note = f' <span class="mail-pj-note">{e(note.rstrip(")"))}</span>' if note else ""
        pj = f'<p class="mail-pj"><span class="mail-trombone" aria-hidden="true">📎</span> <span class="mail-pj-nom">{e(fichier.strip())}</span>{note}</p>'
    return f"""<div class="mail-entete">
  <span class="avatar" aria-hidden="true">{e(nom[:1].upper())}</span>
  <div class="mail-qui">
    <p class="mail-de"><strong>{e(nom)}</strong>{adresse}</p>
    {''.join(dest)}
  </div>
  <p class="mail-date">{e(m.get("date", ""))}</p>
</div>
{pj}"""


def rendre_conversation(texte, b):
    """Conversation Teams : chaque « **Nom** · 18:12 » ouvre une bulle."""
    blocs = re.split(r"^\*\*(.+?)\*\* · (\d\d:\d\d)[ \t]*$", texte.strip(), flags=re.M)
    messages, precedent = [], None
    for i in range(1, len(blocs) - 2, 3):
        nom, heure, corps = blocs[i].strip(), blocs[i + 1], blocs[i + 2].strip()
        # Un titre en gras seul sur sa ligne, et les listes collées au texte, deviennent des blocs à part.
        corps = re.sub(r"\A(\*\*[^*\n]+\*\*[^\n]{0,4})\n", r"\1\n\n", corps)
        corps = re.sub(r"(?m)^(?!\s*(?:[-*]|\d+\.) )(.+)\n(?=(?:[-*]|\d+\.) )", r"\1\n\n", corps)
        tete = "" if nom == precedent else (
            f'<p class="conv-tete"><span class="avatar" aria-hidden="true">{e(nom[:1].upper())}</span>'
            f'<strong>{e(nom)}</strong></p>')
        messages.append(f"""<li class="conv-msg">{tete}
  <p class="conv-heure"><span class="visuellement-cache">{e(nom)}, </span>{heure}</p>
  <div class="bulle bulle-doc">{corriger_liens(md_en_html(corps), b, "")}</div>
</li>""")
        precedent = nom
    return f'<ol class="conv" role="list">{"".join(messages)}</ol>'


def rendre_document(b, d):
    fichier = f"{d['nom']}.html"
    if d["meta"].get("canal"):
        corps = rendre_conversation(d["texte"], b)
    else:
        corps = corriger_liens(md_en_html(d["texte"]), b, "")
    if d["type"] in ("teams", "compte-rendu"):
        corps = aerer(corps)
    if d["type"] == "mail":
        # La signature, après « -- », passe en petit et en gris.
        corps = re.sub(r"<p>--<br />\s*(.*?)</p>", r'<div class="signature"><p>\1</p></div>', corps, flags=re.S)
    if d["type"] == "teams":
        # Dans la transcription, le nom de chaque personne prend la couleur de son organisation.
        for nom, couleur in couleurs_participants(d).items():
            corps = corps.replace(f"<p><strong>{e(nom)}</strong> ·", f'<p><strong class="orateur p-{couleur}">{e(nom)}</strong> ·')
        corps = re.sub(r"</strong> · (\d\d:\d\d)<br />", r'</strong> <span class="heure">\1</span><br />', corps)
    avertissement = ""
    if d["type"] == "rendu":
        lien = d["meta"].get("formulaire", "").strip()
        corps += (f'<p><a class="bouton" href="{e(lien)}">Envoyer mon rendu</a></p>' if lien else
                  '<p class="encart">L\'envoi des rendus ouvre bientôt.</p>')
    if d["type"] == "debrief":
        avertissement = ('<p class="encart">Ce debrief dévoile les pièges du dossier. '
                         'Si tu n\'as pas encore fait le brief, fais-le d\'abord.</p>')
    if d["type"] == "mail":
        surtitre = f'<p class="surtitre">{pastille_type("mail")}</p>'
        haut = entete_mail(d["meta"])
    else:
        surtitre, haut = "", proprietes_document(d)
    contenu = f"""<article aria-labelledby="titre-doc">
  {surtitre}<h1 id="titre-doc">{e(d['titre'])}</h1>
  {haut}
  {avertissement}
  <div class="prose doc-{e(d['type'])}">
{corps}
  </div>
</article>
{suivant_precedent(b, fichier)}"""
    return page(d["titre"], contenu, racine="../../", cote=barre_laterale(b, fichier))


def version(f):
    """Empreinte courte du fichier : change l'adresse quand le fichier change, pour éviter le cache du navigateur."""
    return hashlib.md5(f.read_bytes()).hexdigest()[:8]


def rendre_ressources(b, taille_zip, apercus, textes):
    racine = b["dossier"] / "ressources"
    groupes = {}
    for f in b["ressources"]:
        dossier = " / ".join(f.relative_to(racine).parts[:-1])
        groupes.setdefault(dossier, []).append(f)

    sections = []
    for dossier in sorted(groupes, key=lambda x: (x != "", x.lower())):
        cartes = []
        for f in sorted(groupes[dossier], key=lambda x: x.name.lower()):
            rel = "/".join(f.relative_to(racine).parts)
            ext = f.suffix.lstrip(".").upper() or "?"
            v = version(f)
            if rel in apercus:
                vignette = f'<img src="{e(apercus[rel])}?v={v}" alt="" loading="lazy">'
            else:
                vignette = f'<span class="carte-ext" aria-hidden="true">{e(ext)}</span>'
            texte = (f'<a class="carte-texte" href="{e(textes[rel])}">Version texte</a>'
                     if rel in textes else "")
            cartes.append(f"""<li class="carte">
  <a class="carte-lien" href="ressources/{e(rel)}?v={v}">
    <span class="carte-vignette">{vignette}</span>
    <span class="carte-nom">{e(f.name)}</span>
  </a>
  <span class="carte-info">{pastille(ext, COULEURS_FICHIER.get(ext, "gris"))} {taille_lisible(f.stat().st_size)}</span>
  {texte}
</li>""")
        titre = e(dossier) if dossier else "À la racine du dossier"
        sections.append(f"""<section class="groupe">
  <h2>{titre}</h2>
  <ul class="cartes" role="list">{''.join(cartes)}</ul>
</section>""")

    nb_dossiers = len({f.parent for f in b["ressources"]} - {racine})
    contenu = f"""<h1>Dossier envoyé par le client</h1>
{proprietes([
    ("Envoyé par", e(b['client'])),
    ("Contenu", f"{len(b['ressources'])} fichiers dans {nb_dossiers} dossiers"),
    ("Taille", e(taille_zip)),
])}
<p><a class="bouton" href="{e(b['zip'])}">Tout télécharger (ZIP, {taille_zip})</a></p>
<p class="aide">Chaque fichier s'ouvre aussi seul. Les PDF ont une version texte, lisible avec un lecteur d'écran.</p>
{''.join(sections)}
{suivant_precedent(b, 'ressources.html')}"""
    return page(f"Dossier client, {b['client']}", contenu, racine="../../",
                cote=barre_laterale(b, "ressources.html"))


def rendre_texte_pdf(b, f, chemin_pdf, profondeur):
    """Version HTML d'un PDF, pour les lecteurs d'écran et la lecture rapide."""
    racine = "../" * profondeur
    pages_html = []
    with pymupdf.open(f) as doc:
        for i, p in enumerate(doc, 1):
            blocs = [bl[4].strip() for bl in p.get_text("blocks") if bl[4].strip()]
            paras = "".join(f"<p>{e(t).replace(chr(10), '<br>')}</p>" for t in blocs) or "<p>(page sans texte)</p>"
            pages_html.append(f'<section><h2>Page {i}</h2>{paras}</section>')
    contenu = f"""<h1>{e(f.name)}</h1>
{proprietes([("Type", "Version texte d'un PDF du dossier client"),
             ("Fichier d'origine", f'<a href="{e(racine)}{e(chemin_pdf)}">{e(f.name)}</a>')])}
<div class="prose texte-pdf">
{''.join(pages_html)}
</div>"""
    return page(f"{f.name} (version texte)", contenu, racine=racine + "../../",
                cote=barre_laterale(b, "ressources.html", base=racine))


def rendre_archives(briefs):
    if briefs:
        rangs = "".join(f"""<li>
  <a class="rang" href="brief/{e(b['slug'])}/index.html#haut">
    <span class="rang-type">{pastille(b['livrable'].split('(')[0].strip(), 'bleu')}</span>
    <span class="rang-titre">{e(b['titre'])}</span>
    <span class="rang-info">{date_fr(b['publication'])}</span>
  </a>
</li>""" for b in briefs)
        corps = f'<ul class="rangs">{rangs}</ul>'
    else:
        corps = "<p>Pas encore de brief publié.</p>"
    gauche = """<div class="titre-page">
<h1>Archives</h1>
<p class="chapeau">Tous les briefs publiés, du plus récent au plus ancien, avec leur debrief.</p>
</div>"""
    return page("Archives", corps, actif="archives", cote=gauche)


def legende_rendu(b, r):
    return f"{b['client']}, par {r['nom']}"


def rendre_galerie(briefs):
    """Tous les rendus publiés, en grille de deux, du plus récent au plus ancien."""
    tuiles = []
    for b in briefs:
        for i, r in enumerate(b["rendus"]):
            ancre = f' id="{e(b["slug"])}"' if i == 0 else ""
            couverture = f"brief/{b['slug']}/rendus/{r['slug']}/{r['images'][0].name}"
            tuiles.append(f"""<li class="tuile"{ancre}>
  <a href="brief/{e(b['slug'])}/rendus/{e(r['slug'])}.html#haut">
    <img src="{e(couverture)}" alt="" loading="lazy">
    <span class="tuile-legende">{e(legende_rendu(b, r))}</span>
  </a>
</li>""")
    if tuiles:
        corps = f'<ul class="grille-rendus" role="list">{"".join(tuiles)}</ul>'
    else:
        corps = '<p class="vide">Les premiers rendus arrivent bientôt.</p>'
    contenu = f"""<div class="plein page-rendus">
<h1 class="visuellement-cache">Les rendus des designers</h1>
{corps}
</div>"""
    return page("Rendus", contenu, actif="rendus", plein=True,
                description="Les rendus des designers sur les briefs de Brief & Rebrief.")


def rendre_rendu(b, r):
    """Un rendu : les crédits à gauche, en bas ; les visuels à droite, les uns sous les autres."""
    m = r["meta"]
    n = len(r["images"])
    images = "".join(
        f'<img src="{e(r["slug"])}/{e(f.name)}" alt="Visuel {i} sur {n} du rendu de {e(r["nom"])}"'
        f'{" loading=\"lazy\"" if i > 1 else ""}>' for i, f in enumerate(r["images"], 1))
    nom = e(r["nom"])
    if m.get("lien"):
        nom = f'<a href="{e(m["lien"])}">{nom}</a>'
    lignes = [("Brief", f'<a href="../index.html#haut">{e(b["titre"])}</a>'),
              ("Publié le", e(date_fr(b["publication"])))]
    for morceau in (x.strip() for x in m.get("credits", "").split(";")):
        role, _, qui = morceau.partition(":")
        if qui.strip():
            lignes.append((e(role.strip()), e(qui.strip())))
    credits = "".join(f"<div><dt>{a}</dt><dd>{v}</dd></div>" for a, v in lignes)
    contenu = f"""<div class="plein rendu">
  <div class="rendu-credits">
    <p class="rendu-retour"><a href="../../../rendus.html#haut">← Tous les rendus</a></p>
    <div class="rendu-bas">
      <h1>{e(b['client'])}</h1>
      <p class="rendu-par">Par {nom}</p>
      <dl class="rendu-liste">{credits}</dl>
    </div>
  </div>
  <div class="rendu-images">{images}</div>
</div>"""
    return page(f"{b['client']}, par {r['nom']}", contenu, racine="../../../", actif="rendus", plein=True,
                description=f"Rendu de {r['nom']} sur le brief {b['titre']}.")


def rendre_page_simple(source, titre, actif=""):
    _, texte = lire_markdown(source)
    # Le titre « # … » du fichier passe dans la moitié gauche.
    m = re.match(r"\s*#\s+(.+)\n", texte)
    if m:
        titre_page, texte = m.group(1).strip(), texte[m.end():]
    else:
        titre_page = titre
    contenu = f"""<div class="prose page-{e(source.stem)}">
{md_en_html(texte)}
</div>"""
    return page(titre, contenu, actif=actif, cote=f'<div class="titre-page"><h1>{e(titre_page)}</h1></div>')


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------

def zipper(b, destination):
    racine = b["dossier"] / "ressources"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for f in b["ressources"]:
            z.write(f, Path(b["slug"]) / f.relative_to(racine))


def fabriquer_apercus(b, sortie):
    """Vignettes des images et de la première page des PDF. Renvoie {chemin: url}."""
    racine = b["dossier"] / "ressources"
    apercus = {}
    for f in b["ressources"]:
        rel = "/".join(f.relative_to(racine).parts)
        ext = f.suffix.lower()
        cible = sortie / "apercus" / (rel + ".jpg")
        try:
            if ext in IMAGES:
                with Image.open(f) as img:
                    img = img.convert("RGB")
                    img.thumbnail((LARGEUR_APERCU, LARGEUR_APERCU))
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    img.save(cible, quality=78)
            elif ext == ".pdf":
                with pymupdf.open(f) as doc:
                    p = doc[0]
                    zoom = LARGEUR_APERCU / p.rect.width
                    pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    pix.save(str(cible.with_suffix(".png")))
                    cible = cible.with_suffix(".png")
            elif ext == ".svg":
                apercus[rel] = f"ressources/{rel}"
                continue
            else:
                continue
        except Exception as err:  # un fichier abîmé ne doit pas bloquer le site
            print(f"  ! aperçu impossible pour {rel} : {err}")
            continue
        apercus[rel] = "/".join(cible.relative_to(sortie).parts)
    return apercus


def fabriquer_textes(b, sortie):
    """Une page HTML lisible pour chaque PDF du dossier. Renvoie {chemin: url}."""
    racine = b["dossier"] / "ressources"
    textes = {}
    for f in b["ressources"]:
        if f.suffix.lower() != ".pdf":
            continue
        rel = "/".join(f.relative_to(racine).parts)
        cible = sortie / "texte" / (rel + ".html")
        cible.parent.mkdir(parents=True, exist_ok=True)
        profondeur = len(cible.relative_to(sortie).parts) - 1
        try:
            cible.write_text(rendre_texte_pdf(b, f, f"ressources/{rel}", profondeur), encoding="utf-8")
        except Exception as err:
            print(f"  ! version texte impossible pour {rel} : {err}")
            continue
        textes[rel] = "/".join(cible.relative_to(sortie).parts)
    return textes


def construire(montrer_tout=False):
    aujourd_hui = dt.date.today()
    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    SORTIE.mkdir()
    shutil.copytree(STATIQUE, SORTIE, dirs_exist_ok=True)

    briefs = []
    for dossier in sorted(p for p in BRIEFS.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        b = charger_brief(dossier, aujourd_hui, montrer_tout)
        if not b:
            continue
        if not b["publication"]:
            print(f"  ! {dossier.name} ignoré : date de publication manquante ou mal écrite (format 2026-10-19)")
            continue
        if b["publication"] > aujourd_hui and not montrer_tout:
            print(f"  · {dossier.name} programmé pour le {date_fr(b['publication'])}, pas encore en ligne")
            continue
        if not b["message"]:
            print(f"  ! {dossier.name} : pas de document « type: message », l'accroche de brief.md le remplace")
        briefs.append(b)

    briefs.sort(key=lambda b: (b["publication"], b["slug"]), reverse=True)
    for b in briefs:
        sortie = SORTIE / "brief" / b["slug"]
        sortie.mkdir(parents=True)
        (sortie / "index.html").write_text(rendre_message(b, "../../", "", accueil=b is briefs[0]), encoding="utf-8")
        for d in b["documents"] + [x for x in (b["rendu"], b["debrief"]) if x]:
            (sortie / f"{d['nom']}.html").write_text(rendre_document(b, d), encoding="utf-8")
        if b["ressources"]:
            shutil.copytree(b["dossier"] / "ressources", sortie / "ressources")
            zipper(b, sortie / b["zip"])
            taille_zip = taille_lisible((sortie / b["zip"]).stat().st_size)
            apercus = fabriquer_apercus(b, sortie)
            textes = fabriquer_textes(b, sortie)
            (sortie / "ressources.html").write_text(rendre_ressources(b, taille_zip, apercus, textes), encoding="utf-8")
        if b["rendus"]:
            (sortie / "rendus").mkdir()
            for r in b["rendus"]:
                (sortie / "rendus" / r["slug"]).mkdir()
                for f in r["images"]:
                    shutil.copy2(f, sortie / "rendus" / r["slug"] / f.name)
                (sortie / "rendus" / f"{r['slug']}.html").write_text(rendre_rendu(b, r), encoding="utf-8")
        print(f"  ✓ {b['slug']}" + (" (avec debrief)" if b["debrief"] else "")
              + (f", {len(b['rendus'])} rendu(s)" if b["rendus"] else ""))

    if briefs:
        actuel = briefs[0]
        accueil = rendre_invitation(actuel)
    else:
        accueil = page(NOM_SITE, "<p>Le premier brief arrive lundi.</p>", actif="semaine")
    (SORTIE / "index.html").write_text(accueil, encoding="utf-8")
    (SORTIE / "archives.html").write_text(rendre_archives(briefs), encoding="utf-8")
    (SORTIE / "rendus.html").write_text(rendre_galerie(briefs), encoding="utf-8")
    (SORTIE / "a-propos.html").write_text(rendre_page_simple(PAGES / "a-propos.md", "À propos", "a-propos"), encoding="utf-8")
    (SORTIE / "mentions-legales.html").write_text(rendre_page_simple(PAGES / "mentions-legales.md", "Mentions légales"), encoding="utf-8")
    (SORTIE / ".nojekyll").write_text("")
    print(f"Site construit dans {SORTIE.name}/ : {len(briefs)} brief(s) en ligne.")


if __name__ == "__main__":
    construire(montrer_tout="--tout" in sys.argv)
