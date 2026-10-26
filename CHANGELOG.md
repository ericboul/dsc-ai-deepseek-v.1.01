# Journal des versions

## 2.0.1 — fournisseurs locaux & microphone

- **Fournisseurs locaux dans l'interface** : « FastFlowLM — NPU local (flm serve) »
  (URL `127.0.0.1:52625/v1`, modèle `qwen3.5:4b`) et « LM Studio — local » ; aucune clé
  demandée, URL et modèle pré-remplis. Même choix dans `INSTALLER-TOUT` (options 6 et 7).
- **Choix du microphone** : liste de tous les micros (WASAPI en priorité, MME en repli),
  bouton « Rafraîchir la liste des micros », sélection enregistrée immédiatement, repli
  automatique quand un casque Bluetooth refuse l'endpoint WASAPI.
- Icône de l'application = badge « Le Lien Neural » ; logo affiché dans l'interface.

## 2.0 « RYZEN » — octobre 2026

Version majeure : le copilote **agit** sur l'avion, montre les touches, pilote le menu
Jester du F-14 et peut tourner **entièrement en local sur le NPU**.

### Ajouté

- **Catalogue complet des commandes** (`dcs_keys.py`) : profils DCS + affectations du
  joueur, libellés traduits par les fichiers de langue de DCS, recherche en français
  (poids des mots rares, synonymes, direction monter/sortir). 971 commandes sur F/A-18C,
  1077 sur F-14BU, 856 sur F-15E, 757 sur Ka-50 III.
- **Carré de la touche** (`overlay.py`) : fenêtre Win32/GDI au-dessus de DCS, clic
  traversant, sans vol de focus — indispensable car le Python embarqué n'a pas tkinter.
- **Exécution en trois niveaux** (`command_bridge.py`) : touche du profil →
  commande cockpit (`GetDevice:performClickableAction` via l'environnement export) →
  commande simulateur générique, signalée comme non confirmée.
- **Numéros de devices/commandes** (`dcs_devices.py`) : rejeu des compteurs de
  `devices.lua` / `command_defs.lua`, héritages de modules inclus (F-14BU → F14).
  Validation croisée avec les `.diff.lua` écrits par DCS : 38/38 (F/A-18C), 29/29 (F-14BU).
- **Menu Jester / Iceman** (`jester.py`) : ouvrir, choisir 1-8, fermer, chemins appris
  par appareil (`jester_menu.json`), et lecture des numéros à la voix.
- **Chemin direct sans IA** (`fastpath.py`) : les commandes avion sont reconnues de façon
  déterministe (~0,2 s) — un modèle 4B local ne peut plus les casser.
- **IA locale sur NPU** : `flm serve qwen3.5:4b` (FastFlowLM) sur `127.0.0.1:52625`,
  aucune clé API, aucune donnée envoyée. Cloud toujours possible au choix.
- **Rôle Instructeur** (« Ryzen ») : décollage, atterrissage, combat, une étape à la fois,
  touche affichée, valeur à tenir.
- **Outils du cerveau** : `press_control`, `show_control`, `list_controls`, `autopilot`,
  `jester`.
- **Interface web** : carte « Commandes de l'avion & carré des touches »
  (`/api/commands`, `/api/command`, `/api/commands_info`), pied de page auteur.
- **Documentation** : dossier de présentation PDF (8 pages), fiche rapide,
  référence des commandes vocales.

### Corrigé

- Les modules « Update » héritent désormais du profil d'origine (`external_profile`) :
  catalogue F-14BU passé de 417 à 1077 commandes (pilote auto, Jester, radar…).
- Une adresse locale (`127.0.0.1`) n'exige plus de clé API.
- « pilote automatique » sans mode ne déclenche plus la palette de coupure : le copilote
  demande le mode.
- Le copilote ne prétend plus avoir exécuté une commande qu'il n'a pas pu envoyer.
- Les entrées « caméra / vue / chat » ne sont plus proposées comme commandes d'avion.

### Identité

- Renommage complet en **DCS RYZEN Copilote**, nouveau logo « Le Lien Neural »
  (`.svg`, `.png`, `.ico`) appliqué à l'exe, à la fenêtre et à la documentation.
- Crédits : **Eric Boulianne** (création, développement, identité visuelle),
  projet d'origine *dsc-ai-deepseek* de Snurpsss.

---

## 1.01 — adaptation DeepSeek

- Adaptation du projet d'origine à l'API DeepSeek (fournisseur par défaut).
- Personas multiples, pont Lua, synthèse Piper, reconnaissance Whisper.
