# Installation — DCS RYZEN Copilote

*Windows 10/11 · DCS World (version courante) · aucune installation système de Python.*

---

## 1. Prérequis

| Élément | Détail |
|---|---|
| DCS World | installé et lancé au moins une fois (dossiers `Saved Games\DCS`) |
| Windows | 10 ou 11, 64 bits |
| Espace disque | ~6 Go (Python embarqué, Whisper, 9 voix Piper, modèles) |
| Micro | casque ou micro USB, réglé dans l'interface |
| Cerveau (au choix) | NPU local (`flm`), LM Studio local, Ollama, ou API cloud |

---

## 2. Installation automatique

1. Décompresse le dossier **où tu veux** (portable), par exemple `D:\eb dsc ai deepseek`.
2. Double-clique **`INSTALLER-TOUT.bat`**.
3. Choisis le fournisseur d'IA :
   - `1` DeepSeek (cloud, clé sur <https://platform.deepseek.com/api_keys>) ;
   - `2` OpenAI ; `3` Anthropic ; `4` URL personnalisée (LM Studio / NPU local) ;
   - `5` Ollama (local, sans clé).
4. L'installateur met en place : Python embarqué, bibliothèques, Piper + 9 voix,
   modèle Whisper, pont Lua dans `Saved Games\DCS\Scripts`, raccourci Bureau.

> Aucun fichier système n'est modifié, sauf les deux `.lua` du pont DCS
> (`Saved Games\DCS\Scripts\`) — une sauvegarde de `Export.lua` est créée.

---

## 3. Cerveau local sur NPU (recommandé sur Ryzen AI)

```bat
flm serve qwen3.5:4b
```

Fenêtre à laisser ouverte. Le serveur écoute sur `http://127.0.0.1:52625/v1`.

Dans l'interface (`Cerveau (IA)`) :

| Champ | Valeur |
|---|---|
| Fournisseur | **Personnalisé (URL + clé)** |
| URL API | `http://127.0.0.1:52625/v1` |
| Modèle | `qwen3.5:4b` |
| Clé | *vide* (une adresse locale n'en demande pas) |

Variante LM Studio : URL `http://127.0.0.1:1234/v1`, modèle = nom affiché dans LM Studio.

---

## 4. Premier vol

1. Lance **DCS RYZEN Copilote** (raccourci Bureau).
2. L'interface s'ouvre sur <http://127.0.0.1:5001> ; règle **micro**, **push-to-talk**
   (défaut `Tab`), **voix**.
3. Démarre DCS et **entre en mission** (le pont ne fonctionne qu'en vol, pas en pause).
4. Maintiens le push-to-talk et dis : « **sors le train** ».
   → le train sort, la touche s'affiche dans un carré au-dessus du jeu.

---

## 5. Vérifications utiles

| Test | Où |
|---|---|
| Interface répond | carte « Commandes de l'avion » : avion détecté + nombre de commandes |
| Pont DCS vivant | bouton « Tester » (carte 6) : message affiché dans DCS |
| Cerveau | `curl http://127.0.0.1:52625/v1/models` |
| Micro | bouton « Tester le micro » (4 s) |
| Voix | bouton « Tester la voix » |

---

## 6. Désinstallation

1. Ferme l'application (fenêtre du copilote).
2. Supprime les `.lua` du pont : `Saved Games\DCS\Scripts\Hooks\dcs_claude_control.lua`
   et `Saved Games\DCS\Scripts\dcs_claude_export.lua` (restaure `Export.lua` depuis
   `Saved Games\DCS\Scripts\eb_backup` si besoin).
3. Supprime le dossier de l'application et le raccourci du Bureau.

`config.json`, les clés et tes réglages restent dans le dossier : rien n'est écrit ailleurs.
