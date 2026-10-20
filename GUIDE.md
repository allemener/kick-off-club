# Guide de Kick-off Club

Ce guide explique comment mettre le site en ligne (une seule fois), puis comment ajouter un brief chaque semaine. Tout se fait depuis le site de GitHub, dans le navigateur. Aucun logiciel à installer.

---

## Partie 1. Mettre le site en ligne (une seule fois, 10 minutes)

Avant de commencer, ouvre `pages/mentions-legales.md` et remplace `[ADRESSE E-MAIL À COMPLÉTER]` par une adresse de contact.

### Étape 1. Créer le dépôt

1. Connecte-toi sur [github.com](https://github.com).
2. En haut à droite, clique sur **+** puis **New repository**.
3. **Repository name** : `kick-off-club` (sans accent ni espace, c'est ce qui apparaîtra dans l'adresse du site).
4. Coche **Public**.
5. Ne coche rien d'autre. Clique sur **Create repository**.

### Étape 2. Envoyer les fichiers du site

1. Sur la page du dépôt vide, clique sur le lien **uploading an existing file**.
2. Ouvre le dossier `kick-off-club` sur ton ordinateur, sélectionne **tout son contenu** (pas le dossier lui-même) et glisse-le dans la fenêtre GitHub.
   - Le dossier `.github` est caché sur Mac. Dans le Finder, appuie sur **Cmd + Maj + .** pour afficher les fichiers cachés. Il doit être envoyé, c'est lui qui publie le site.
3. En bas, dans **Commit changes**, écris par exemple « Première version du site » et clique sur **Commit changes**.

### Étape 3. Activer GitHub Pages

1. Dans le dépôt, clique sur **Settings** (l'onglet avec un engrenage).
2. Dans le menu de gauche, clique sur **Pages**.
3. Sous **Build and deployment**, dans **Source**, choisis **GitHub Actions**.

### Étape 4. Vérifier

1. Clique sur l'onglet **Actions** du dépôt. Une ligne « Publier le site » tourne (rond jaune).
2. Quand elle passe au vert (1 à 2 minutes), retourne dans **Settings > Pages** : l'adresse du site s'affiche en haut, du type `https://allemener.github.io/kick-off-club/`.

Si la ligne n'apparaît pas dans **Actions**, va dans **Actions**, clique sur **Publier le site** à gauche, puis sur **Run workflow**.

---

## Partie 2. Ajouter un brief

Un brief, c'est **un dossier** dans `briefs/`. Le site fabrique tout seul la page, le sommaire et le zip.

### Ce que contient un dossier de brief

```
briefs/
  2026-10-26-nom-du-client/        ← le nom du dossier devient l'adresse de la page
    brief.md                       ← la fiche (obligatoire)
    00-message.md                  ← le message de l'AM, c'est la page d'accueil du brief
    01-resume-teams.md             ← les autres pièces, dans l'ordre des numéros
    02-compte-rendu.md
    03-mail-client.md
    ressources/                    ← tous les fichiers du client, zippés automatiquement
      01_Charte/...
      02_Logos/...
```

Règles pour le nom du dossier : minuscules, chiffres et tirets, **pas d'espace ni d'accent**. Commencer par la date aide à s'y retrouver.

Dans `ressources/`, mets ce que tu veux (PDF, images, Excel, sous-dossiers…), avec des noms de fichiers réalistes. C'est même mieux s'ils sont mal rangés.

### La fiche `brief.md`

Elle n'est pas affichée telle quelle : elle sert au titre de la page et à la liste des archives.

```
---
titre: Brûlerie Ferrand, une nouvelle identité pour une maison de 1958
client: Brûlerie Ferrand
secteur: Café, torréfaction artisanale
livrable: Identité visuelle (logo, couleurs, typographies, premières applications)
publication: 2026-10-19
---
Une phrase de résumé.
```

- La partie entre les deux lignes `---` est la fiche. Garde les mots avant les deux-points tels quels.
- `publication` s'écrit **année-mois-jour**. C'est le lundi où le brief sort.

### Le message de l'AM (`00-message.md`)

C'est ce que voit le visiteur en arrivant : un message Teams ou Slack de la personne qui lui confie le projet, avec des liens vers les pièces.

```
---
titre: Message de Camille
type: message
de: Camille Roussel (cheffe de projet)
role: la cheffe de projet
canal: Teams, conversation privée
date: lundi 19 octobre 2026, 09:05
---
Hello ! Je te passe le projet Brûlerie Ferrand.

- le [récap Teams du kick-off](01-resume-teams)
- le [dossier qu'ils nous ont envoyé](ressources), ou [tout en zip](ressources.zip)
```

Pour faire un lien vers une pièce, écris `[le texte du lien](nom-du-fichier)`, avec le nom du fichier **sans** `.md`. Deux noms spéciaux : `ressources` ouvre le dossier client, `ressources.zip` télécharge le zip. Pour un canal Slack, écris par exemple `canal: Slack, #projet-ferrand`. Le champ `role` donne le titre de la section : `role: la cheffe de projet` affiche « Le message de la cheffe de projet », `role: le chef de projet` affiche « Le message du chef de projet ».

Si tu oublies de faire un lien vers une pièce, elle est quand même listée sous le message, dans « Pièces partagées ».

### L'accroche de la page d'accueil

L'accueil du site montre un message Teams de la cheffe de projet qui te propose le projet. Tu cliques sur une réponse (« Carrément, envoie ! »…) et tu entres dans le brief. Le texte de ce premier message est le champ `accroche` de `brief.md`. Sans accroche, le site en écrit une à partir du client et du livrable.

### Les autres pièces

Chaque autre fichier `.md` devient une page. Le `type` change sa présentation :

| type | Affiché comme | Champs possibles |
|---|---|---|
| `teams` | Récapitulatif de réunion Teams | `date`, `duree`, `organisateur`, `participants` (séparés par des points-virgules) |
| `compte-rendu` | Compte rendu | `auteur`, `date`, `version` |
| `mail` | E-mail, présenté comme dans une messagerie (expéditeur, destinataires, pièce jointe, signature après `--`) | `de`, `a`, `cc`, `date`, `objet`, `pieces` |
| `conversation` | Message Teams en bulles (par exemple la note d'intention du directeur de création) | `de`, `canal`, `date` |
| `note` | Note | `auteur`, `date`, `version` |

Dans une `conversation`, chaque bulle commence par une ligne `**Prénom Nom** · 18:12`. Une première ligne en gras devient le titre de la bulle. Le debrief peut aussi s'écrire ainsi : ajoute `de`, `canal` et `date` dans son en-tête.

Dans le récap Teams et le compte rendu, les lignes du type `- **Libellé** : texte` s'affichent avec le libellé posé au-dessus du texte, pour aérer.

Ajoute aussi `court:` dans l'en-tête de chaque pièce : c'est le libellé court affiché dans le sommaire (par exemple `court: Le compte rendu`).

Sous la fiche, le texte s'écrit en Markdown : `## Titre`, `**gras**`, `- liste`, `> citation`, et des tableaux. Les liens entre pièces marchent aussi ici. Dans le dossier client, le site fabrique tout seul les vignettes (images et première page des PDF) et une **version texte** de chaque PDF, lisible avec un lecteur d'écran.

### Les consignes de rendu (`rendu.md`)

Le fichier `rendu.md` décrit ce que le designer doit rendre : des planches de DA finales, leur format, leur ordre, la date limite. Dans l'en-tête, `date_limite` et `format` s'affichent en haut de la page, et `formulaire` reçoit le lien de ton formulaire d'envoi. Tant que `formulaire` est vide, la page affiche « L'envoi des rendus ouvre bientôt ». Le modèle contient un exemple.

### Publier les rendus (`rendus/`)

Chaque semaine, tu choisis les rendus à montrer. Dans le dossier du brief, crée un dossier `rendus/`, puis **un sous-dossier par designer** (par exemple `rendus/marie-dupont/`) avec :

- ses visuels en JPG ou PNG, nommés dans l'ordre (`01.jpg`, `02.jpg`…). Le premier sert de couverture dans la page **Rendus** ;
- un fichier `credits.md` : `nom` (nom ou pseudo affiché), `lien` (portfolio, facultatif), `credits` (qui a fait quoi, séparé par des points-virgules, par exemple `Identité visuelle : Marie Dupont; Photos : Unsplash`). Pas de texte sous l'en-tête : la page du rendu affiche seulement le client, le nom et les crédits.

Le site fabrique la page du rendu (visuels à droite, crédits en bas à gauche) et l'ajoute à la grille de l'onglet **Rendus**. Un exemple est dans `briefs/_modele/rendus/`.

### Le debrief (`debrief.md`)

Le fichier `debrief.md` est le debrief du directeur de création : les pièges du brief et le brief remis au propre, écrits à la première personne. Il reste caché et **sort automatiquement le lundi suivant** la publication du brief. Pour une autre date, ajoute `publication: 2026-11-02` dans son en-tête.

Le dossier `briefs/_modele/` contient un exemple de chaque fichier : copie-le pour démarrer. Il n'apparaît pas sur le site.

### Envoyer le brief sur GitHub

1. Prépare le dossier du brief sur ton ordinateur.
2. Sur GitHub, ouvre le dossier **briefs** du dépôt.
3. Clique sur **Add file > Upload files**.
4. Glisse **le dossier du brief entier** dans la fenêtre (Chrome, Edge et Firefox gardent les sous-dossiers).
5. Clique sur **Commit changes**.

Le site se met à jour tout seul en 1 à 2 minutes (onglet **Actions** pour suivre).

---

## Partie 3. Programmer les briefs à l'avance

Tu peux déposer plusieurs semaines d'avance. Un brief dont la date de `publication` est dans le futur reste caché. Chaque lundi à 6 h (heure de Paris en hiver), le site se reconstruit et affiche les nouveaux.

L'accueil montre toujours le brief le plus récent. Tous les briefs publiés sont listés dans la page **Archives**. Donne à chaque brief la date du lundi où il doit sortir (un brief par lundi).

---

## Partie 4. Fabriquer un brief plus vite

La méthode complète, le catalogue de pièges et la check-list de relecture sont dans **[RECETTE.md](RECETTE.md)**.

## Partie 5. Corriger un brief

Ouvre le fichier sur GitHub, clique sur le crayon (**Edit this file**), corrige, puis **Commit changes**. Pour remplacer un fichier du client, ouvre son dossier dans `ressources/` et utilise **Add file > Upload files** avec le même nom.

Pour retirer un brief, ouvre son dossier, clique sur **…** en haut à droite, puis **Delete directory**.

---

## Si quelque chose ne marche pas

- **Rond rouge dans l'onglet Actions** : clique dessus, puis sur **construire**. Le message en clair dit souvent le problème, par exemple « date de publication manquante ou mal écrite ».
- **Le brief n'apparaît pas** : vérifie la date de `publication` (format `2026-10-26`) et qu'il y a bien un fichier `brief.md` dans le dossier.
- **Les accents s'affichent mal** : enregistre le fichier en UTF-8 (c'est le cas par défaut dans GitHub et dans la plupart des éditeurs).

## Voir le site sur ton ordinateur (facultatif)

Si Python est installé : dans le dossier du site, lance `pip install -r requirements.txt` puis `python3 build.py --tout`, et ouvre `_site/index.html`. L'option `--tout` montre aussi les briefs programmés.
