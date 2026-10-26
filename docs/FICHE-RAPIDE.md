# Fiche rapide — DCS RYZEN Copilote

*À garder à côté du HOTAS. Version 2.0 · créé par Eric Boulianne (développeur web & graphiste) · MIT.*

---

## 1. Démarrer

| Étape | Action |
|---|---|
| 1 | `INSTALLER-TOUT.bat` (une seule fois) |
| 2 | Lancer **DCS RYZEN Copilote** (raccourci Bureau ou `DCS-RYZEN-Copilote.exe`) |
| 3 | Interface : <http://127.0.0.1:5001> |
| 4 | Cerveau local : `flm serve qwen3.5:4b` (fenêtre à laisser ouverte) |
| 5 | Push-to-talk (défaut : `Tab`), tu parles |

Le copilote ne démarre **qu'une fois** : si tu relances, il ouvre l'interface existante.

---

## 2. Commandes de l'avion — exemples qui marchent

| Tu dis | Ce qu'il fait |
|---|---|
| « sors le train » / « rentre le train » | `Maj+G` / `Ctrl+G` |
| « volets » / « montre-moi les volets » | affiche la touche sans agir |
| « sors les aérofreins » | `Maj+B` |
| « active le master arm » | `M` (F/A-18C) |
| « allume le phare » / « allume les feux » | touche du phare / feux extérieurs |
| « montre la crosse » | affiche la touche de la crosse |
| « pilote auto maintien d'altitude » | interrupteur AP de l'appareil (F-14, etc.) |
| « pilote auto en palier » / « altitude et cap » | mode correspondant, si l'appareil l'a |
| « débraye le pilote auto » | coupe le pilote automatique |

Règle : un verbe d'**action** (« sors », « mets », « active », « rentre »…) = il agit.
Un verbe d'**affichage** (« montre », « affiche », « où est ») = il montre seulement.

---

## 3. F-14 : menu Jester

| Tu dis | Effet |
|---|---|
| « ouvre le menu Jester » | `A` |
| « Jester 3 » / « va sur 3 » | `Ctrl+3` |
| « trois » (menu déjà ouvert) | `Ctrl+3` |
| « ferme le menu Jester » | `Maj+A` |
| « Jester radar » | ouvre, joue le chemin appris, referme |

**Apprendre un chemin** (une fois) : « Jester apprends radar = 1 3 » (ou via l'interface,
outil `jester action=learn`). Ensuite « Jester radar » refait la séquence.

---

## 4. Parler au copilote (rôle Ryzen)

- « Ryzen, je suis en approche finale, qu'est-ce que je fais ? »
- « Ryzen, parle-moi de l'atterrissage sur le Hornet »
- « Ryzen, il me reste combien de temps de vol ? »
- Autres personas : **Overlord** (AWACS), **IceMan** (ailier) — commence par l'indicatif.

---

## 5. Faire vivre la mission (outils IA)

- « fais apparaître deux MiG-29 devant moi à 20 nautiques »
- « mets un site SA-10 à 30 nautiques au nord »
- « marque la cible avec de la fumée rouge »
- « ordonne aux alliés d'engager »
- « donne-moi ma position et mon cap »

---

## 6. Si ça ne répond pas

| Symptôme | Cause / solution |
|---|---|
| « fenêtre DCS introuvable » | DCS n'est pas au premier plan (il refuse d'envoyer des touches ailleurs) |
| silence total | le serveur du cerveau n'écoute pas : `flm serve qwen3.5:4b` |
| la touche s'affiche mais rien ne bouge | l'interrupteur n'a pas de raccourci : lie-le dans Options > Commandes |
| rien au micro | mauvaise entrée audio, ou casque muet (l'interface montre le niveau) |
| pas de télémétrie | deux instances lancées, ou mission non chargée |

---

## 7. Fichiers utiles

- `config.json` — réglages (fournisseur IA, voix, PTT, personas)
- `dcs_keys.py` — catalogue des commandes lues dans DCS
- `jester_menu.json` — chemins Jester appris
- `Saved Games\DCS\Scripts\Hooks\dcs_claude_control.lua` — pont avec la mission
- `docs\DCS-RYZEN-COPILOTE.pdf` — dossier complet
