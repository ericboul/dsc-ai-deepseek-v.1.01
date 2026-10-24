# DCS RYZEN Copilote — installation automatique

**Créé par Eric Boulianne — développeur web & graphiste.**
Projet **open source** (licence MIT) · <https://github.com/ericboul/dsc-ai-deepseek-v1.01>


Copilote vocal pour **DCS World** (reconnaissance vocale locale, voix neuronale,
IA DeepSeek / OpenAI / Anthropic / Ollama), basé sur
[ericboul/dsc-ai-deepseek-v.1.01](https://github.com/ericboul/dsc-ai-deepseek-v.1.01),
livré avec un **installateur tout-en-un** : un seul double-clic installe Python,
les librairies, les voix, le modèle Whisper, le pont DCS et la configuration IA.

Dossier : `D:\eb dsc ai deepseek`

---

## 1. Ce que fait l'installateur

`INSTALLER-TOUT.bat` enchaîne, sans intervention (hors choix du fournisseur et
de la clé API) :

| Étape | Détail | Où |
|---|---|---|
| 1 | Python 3.11 **embarqué** (aucune installation système) | `python\` |
| 2 | Librairies : faster-whisper, flask, pygame, sounddevice, pywin32, httpx… | `libs\` |
| 3 | Piper (synthèse neuronale) + **9 voix prêtes** : 7 françaises (siwis medium/low, tom, upmc, mls, mls_1840, gilles) et 2 anglaises | `piper\` |
| 4 | Modèle Whisper pré-téléchargé (dicte immédiatement, sans attente) | `models\` |
| 5 | Fournisseur IA + clé API → écrit `config.json` (aucune saisie dans l'interface) | racine |
| 6 | Ollama : détection, installation `winget`, `ollama pull` (si choisi) | système |
| 7 | Pont DCS : `.lua` copiés dans `Saved Games\DCS\Scripts` + `Hooks`, `Export.lua` complété (avec sauvegarde) | `%USERPROFILE%\Saved Games\DCS` |
| 8 | Test réel d'un aller-retour avec le modèle | — |
| 9 | Raccourci **DCS RYZEN Copilote** sur le Bureau | Bureau |

Rien n'est installé « pour tout le PC » : tout reste dans le dossier (portable),
sauf le raccourci et les deux `.lua` côté DCS.


---

## 1 bis. Le copilote agit sur TON avion (touches + carré à l'écran)

**Nouveau.** Le copilote lit le catalogue complet des commandes de l'appareil que
tu pilotes (profils DCS + tes affectations HOTAS), traduit en français par DCS
lui-même, et peut :

| Ce que tu dis | Ce qui se passe |
|---|---|
| « sors le train », « rentre le train » | il appuie sur la vraie touche (**Maj+G** / **Ctrl+G**) |
| « volets », « aérofreins », « crosse », « perche » | touche réelle, exécutée |
| « master arm », « armement » | touche réelle (M sur le Hornet) |
| « pilote auto maintien altitude », « assieds-toi en palier », « débraye » | commande DCS (maintien d'altitude / assiette / palier / cap / débrayage) |
| « montre-moi le train » | **il n'exécute rien** : il affiche la touche dans un **carré** |

Le carré s'affiche **par-dessus DCS** (touche en gros + libellé de la commande) et
un rappel s'écrit aussi dans le bandeau du jeu. C'est le mode **instructeur** :
à chaque étape d'une procédure (démarrage, décollage, approche, combat) il montre
la touche, donne la vitesse/l'altitude/le cap à tenir, puis attend ton retour.

Limite honnête : un interrupteur **sans raccourci clavier** (l'autopilote du
Hornet, par exemple) ne peut pas être « pressé » par un logiciel externe — le
copilote te le dit et t'indique la zone du cockpit (+ le bouton HOTAS si tu l'as
lié), au lieu d'inventer.

Où régler ça : interface web → carte **« Commandes de l'avion & carré des touches »**
(chercher / afficher / exécuter, cases « appuyer sur les touches » et « carré à
l'écran », durée d'affichage).


---

## 2. Installation

1. Double-clique **`INSTALLER-TOUT.bat`** (une seule fois, pour installer Python, les librairies,
   les voix, le modèle Whisper et le pont DCS).
2. Choisis le fournisseur d'IA :
   - `1` **DeepSeek** (recommandé) — clé sur <https://platform.deepseek.com/api_keys>
   - `2` OpenAI — <https://platform.openai.com/api-keys>
   - `3` Anthropic Claude
   - `4` **Ollama** (100 % local, gratuite, aucune clé)
   - `5` autre API compatible OpenAI (Mistral, Groq, OpenRouter…) — tu saisis **l'URL de base**,
     le **nom exact du modèle** et ta **clé API** (envoyée en `Authorization: Bearer`)
3. Colle la clé API (saisie masquée, stockée en local dans `deepseek_key.txt`
   ou `openai_key.txt` / `apikey.txt`).
4. Laisse tourner : comptez 5 à 15 min la première fois (téléchargements).
5. À la fin, réponds `O` pour lancer tout de suite, ou plus tard : double-clic
   sur **`DCS-RYZEN-Copilote.bat`** (ou le raccourci du Bureau).

L'interface s'ouvre sur <http://127.0.0.1:5001> ; le copilote démarre en même temps.

### Variante en ligne de commande

```bat
INSTALLER-TOUT.bat -Provider ollama -NoPrompt
INSTALLER-TOUT.bat -Provider deepseek -ApiKey sk-xxxxxxxx -NoPrompt
INSTALLER-TOUT.bat -Provider custom -BaseUrl https://api.mistral.ai/v1 -Model mistral-large-latest
INSTALLER-TOUT.bat -SkipDcs -SkipModels        :: ne pas toucher à DCS / ne pas télécharger Whisper
```

Options : `-Provider` `-ApiKey` `-Model` `-BaseUrl` `-Whisper base|small|medium`
`-SkipModels` `-SkipDcs` `-NoPrompt` `-NoShortcut`.

L'installateur est **idempotent** : relançable à tout moment, il ne retélécharge
que ce qui manque.

---

## 3. Côté DCS

L'installateur fait le nécessaire dans `%USERPROFILE%\Saved Games\DCS` :

- `Scripts\dcs_claude_export.lua` — télémétrie (UDP 127.0.0.1:5010)
- `Scripts\Export.lua` — une ligne `dofile(...)` ajoutée à la fin
- `Scripts\Hooks\dcs_claude_control.lua` — actions en jeu (UDP 127.0.0.1:5011)

Les fichiers existants sont sauvegardés dans `Scripts\eb_backup\`.
Fonctionne aussi avec `DCS.openbeta` s'il existe. Aucun mod, aucune modification
de `MissionScripting.lua`.

> Si DCS n'a jamais été lancé, le dossier `Saved Games\DCS` peut ne pas exister :
> lance DCS une fois, puis relance `INSTALLER-TOUT.bat`.

---

## 4. Changer de fournisseur / de modèle plus tard

### Top Tools AI (top-tools-ai.com)

Préréglage déjà dans l'assistant (**Fournisseur → Top Tools AI**) :

| Réglage | Valeur |
|---|---|
| URL API | `https://top-tools-ai.com/api/v1` |
| Modèle | `Top-Tools-Ai` (512 K de contexte, vision + *tool calls*) |
| Clé API | celle de ton dashboard, envoyée en `Authorization: Bearer` |

Le bouton **« Lister les modèles »** interroge `{URL}/models` et remplit la liste avec les
identifiants réels auxquels ta clé donne droit (utile quand un nouveau modèle sort).

Deux façons :

- **Interface web** → carte « Cerveau (IA) » → fournisseur, modèle, URL, clé.
- **En ligne de commande** :
  ```bat
  python\python.exe eb_configure.py --provider openai --key sk-...
  python\python.exe eb_configure.py --provider ollama --model qwen2.5
  python\python.exe eb_configure.py --show          :: état actuel
  python\python.exe eb_check_llm.py                 :: test de connexion
  ```

Modèles DeepSeek utiles : `deepseek-chat` (rapide, par défaut),
`deepseek-reasoner` (raisonnement).

---

## 5. Fichiers ajoutés au projet

| Fichier | Rôle |
|---|---|
| `DCS-RYZEN-Copilote.exe` | **l'application** : demande la configuration puis démarre le copilote |
| `eb_wizard.py` | source de la fenêtre de configuration (compilée dans l'exe) |
| `eb_apply_setup.py` | applique la configuration (appelé par l'exe, via le python embarqué) |
| `INSTALLER-TOUT.bat` | installateur complet (double-clic) |
| `DCS-RYZEN-Copilote.bat` | lanceur unique (installe si besoin, puis démarre) |
| `eb_install.ps1` | moteur de l'installation (PowerShell) |
| `eb_configure.py` | écrit `config.json` + fichier de clé |
| `eb_check_llm.py` | test de connexion au fournisseur IA |
| `EB-INSTALLATION-LOG.txt` | journal de la dernière installation |
| `LISEZ-MOI-EB.md` | ce document |

---

## 6. Dépannage

| Symptôme | Solution |
|---|---|
| « Python embarque absent » | vérifie la connexion, relance `INSTALLER-TOUT.bat` |
| Traceback `OSError: [WinError 10048]` (port 5010) | une 2ᵉ instance était déjà lancée. Corrigé : le lanceur et `app.py` refusent la 2ᵉ instance et rouvrent l'interface existante. Si ça arrive quand même : gestionnaire des tâches → tue les `python.exe` du dossier, puis relance une seule fois |
| Installation pip qui échoue | proxy/pare-feu ; relance, le cache pip reprend |
| Pas de voix | `piper\piper\piper.exe` présent ? sinon SAPI Windows prend le relais |
| L'IA ne répond pas | relance `python\python.exe eb_check_llm.py` : clé invalide, crédit épuisé ou réseau |
| Rien dans DCS | DCS lancé après l'install ? `Export.lua` contient la ligne `dcs_claude_export` ? le test « Canal DCS » de l'interface ne répond que **en mission** (pas en pause, pas au menu) |
| Repartir de zéro | `reset.bat` (supprime clés, libs, modèles, Python, Piper) puis `INSTALLER-TOUT.bat` |
| Port 5001 occupé | c'est le copilote déjà lancé : le lanceur ouvre simplement l'interface |

Journal détaillé : `EB-INSTALLATION-LOG.txt`.
