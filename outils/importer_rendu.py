"""Récupère un rendu envoyé par le formulaire Tally et le range dans le bon brief.

Utilisé par le bouton « Publier un rendu » (GitHub Actions), mais marche aussi à la main :

    TALLY_API_KEY=... python outils/importer_rendu.py            # le dernier envoi
    TALLY_API_KEY=... python outils/importer_rendu.py "ALI"      # l'envoi de ce pseudo

Le rendu est écrit dans briefs/<brief>/rendus/<pseudo>/ : 01.jpg, 02.jpg… et credits.md.
"""
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
FORMULAIRE = os.environ.get("TALLY_FORM", "WJO85L")
LARGEUR_MAX = 2400


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation, pour comparer des noms tapés à la main."""
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def slug(texte):
    return normaliser(texte).replace(" ", "-") or "designer"


def ouvrir(url, cle=None):
    requete = urllib.request.Request(url, headers={"User-Agent": "brief-rebrief"})
    if cle:
        requete.add_header("Authorization", f"Bearer {cle}")
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return reponse.read()


def charger_envois():
    """Les envois du formulaire, avec le titre de chaque question à côté de la réponse."""
    if os.environ.get("TALLY_JSON"):  # pour tester sans appeler Tally
        donnees = json.loads(Path(os.environ["TALLY_JSON"]).read_text())
    else:
        cle = os.environ.get("TALLY_API_KEY")
        if not cle:
            sys.exit("Il manque la clé Tally (secret TALLY_API_KEY).")
        donnees = json.loads(ouvrir(f"https://api.tally.so/forms/{FORMULAIRE}/submissions?limit=100", cle))
    titres = {q.get("id"): q.get("title") or "" for q in donnees.get("questions", [])}
    envois = []
    for s in donnees.get("submissions", []):
        if s.get("isCompleted") is False:
            continue
        reponses = [(titres.get(r.get("questionId"), ""), r.get("answer")) for r in s.get("responses", [])]
        envois.append({"date": s.get("submittedAt", ""), "reponses": reponses})
    envois.sort(key=lambda e: e["date"], reverse=True)
    return envois


def fichiers(reponse):
    """Les fichiers d'une réponse de type envoi de fichiers : une liste d'objets avec une adresse."""
    if isinstance(reponse, list):
        return [f for f in reponse if isinstance(f, dict) and f.get("url")]
    return []


def texte(reponse):
    if reponse is None:
        return ""
    if isinstance(reponse, list):
        return ", ".join(texte(x) for x in reponse if not isinstance(x, dict))
    return str(reponse).strip()


def trouver(envoi, *mots):
    """La réponse à la première question dont le titre contient un de ces mots."""
    for titre, reponse in envoi["reponses"]:
        t = normaliser(titre)
        if any(m in t for m in mots):
            return reponse
    return None


def lire_envoi(envoi):
    images = []
    for _, reponse in envoi["reponses"]:
        images += fichiers(reponse)
    consentement = trouver(envoi, "accepte", "consent")
    return {
        "nom": texte(trouver(envoi, "pseudo", "ton nom")),
        "brief": texte(trouver(envoi, "brief")),
        "lien": texte(trouver(envoi, "portfolio", "lien", "site")),
        "credits": texte(trouver(envoi, "credit")),
        "consentement": consentement,
        "consentement_trouve": any("accepte" in normaliser(t) or "consent" in normaliser(t)
                                   for t, _ in envoi["reponses"]),
        "images": images,
    }


def trouver_brief(nom):
    """Le dossier du brief dont le client ressemble le plus au nom tapé dans le formulaire."""
    cherche = normaliser(nom)
    for dossier in sorted((RACINE / "briefs").iterdir()):
        fiche = dossier / "brief.md"
        if dossier.name.startswith("_") or not fiche.exists():
            continue
        client = re.search(r"^client:\s*(.+)$", fiche.read_text(encoding="utf-8"), re.M)
        candidats = [normaliser(client.group(1))] if client else []
        candidats.append(normaliser(dossier.name[11:].replace("-", " ")))
        if any(c and (c in cherche or cherche in c) for c in candidats):
            return dossier
    sys.exit(f"Je ne trouve pas de brief qui correspond à « {nom} ».")


def ordre_naturel(f):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", f.get("name", ""))]


def credits_en_ligne(brut):
    """Les crédits tapés librement, remis au format « Rôle : Nom; Rôle : Nom »."""
    morceaux = []
    for ligne in re.split(r"[\n;]+", brut):
        ligne = ligne.strip(" -•\t")
        if not ligne:
            continue
        role, sep, qui = ligne.partition(":")
        morceaux.append(f"{role.strip()[:1].upper()}{role.strip()[1:]} : {qui.strip()}" if sep and qui.strip() else f"Crédits : {ligne}")
    return "; ".join(morceaux)


def main():
    pseudo = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    envois = [lire_envoi(e) for e in charger_envois()]
    if pseudo:
        envois = [e for e in envois if normaliser(e["nom"]) == normaliser(pseudo)]
    if not envois:
        sys.exit(f"Aucun envoi trouvé{' pour ' + pseudo if pseudo else ''} dans le formulaire Tally.")
    rendu = envois[0]

    if rendu["consentement_trouve"] and not rendu["consentement"]:
        sys.exit(f"{rendu['nom']} n'a pas accepté la publication : rien n'est publié.")
    if not rendu["images"]:
        sys.exit(f"L'envoi de {rendu['nom']} ne contient aucune image.")

    brief = trouver_brief(rendu["brief"])
    sortie = brief / "rendus" / slug(rendu["nom"])
    if sortie.exists():
        for f in sortie.iterdir():
            f.unlink()
    sortie.mkdir(parents=True, exist_ok=True)

    for i, f in enumerate(sorted(rendu["images"], key=ordre_naturel), 1):
        image = Image.open(io.BytesIO(ouvrir(f["url"])))
        image = image.convert("RGB")
        if image.width > LARGEUR_MAX:
            image = image.resize((LARGEUR_MAX, round(image.height * LARGEUR_MAX / image.width)), Image.LANCZOS)
        image.save(sortie / f"{i:02d}.jpg", "JPEG", quality=88, optimize=True, progressive=True)

    def entre_guillemets(v):
        return '"' + " ".join(v.replace('"', "’").split()) + '"'

    lignes = ["---", f"nom: {entre_guillemets(rendu['nom'])}"]
    if rendu["lien"].startswith("http"):
        lignes.append(f"lien: {rendu['lien']}")
    credits = credits_en_ligne(rendu["credits"])
    if credits:
        lignes.append(f"credits: {entre_guillemets(credits)}")
    lignes.append("---")
    (sortie / "credits.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(f"Rendu de {rendu['nom']} rangé dans {sortie.relative_to(RACINE)} ({len(rendu['images'])} visuels).")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as sortie_gh:
            sortie_gh.write(f"nom={rendu['nom']}\nbrief={brief.name}\ndossier={sortie.relative_to(RACINE)}\n")


if __name__ == "__main__":
    main()
