# Commandes vocales — référence complète

*DCS RYZEN Copilote v2.0. Les formes ci-dessous sont celles que le copilote reconnaît
**sans IA** (chemin direct, ~0,2 s). Tout le reste passe par le modèle de langage.*

---

## 1. Comment il comprend

1. **Verbe d'action** → il exécute : `sors`, `rentre`, `mets`, `active`, `arme`, `désarme`,
   `ouvre`, `ferme`, `déploie`, `étends`, `baisse`, `lève`, `coupe`, `allume`, `éteins`,
   `largue`, `engage`, `débraye`, `bascule`.
2. **Verbe d'affichage** → il montre seulement : `montre`, `affiche`, `où est`,
   `quelle touche`, `quel bouton`, `explique`.
3. **Sans verbe**, une phrase courte (« les volets », « la crosse ») → il **montre**.
   Il n'actionne jamais un interrupteur sur une phrase ambiguë.

Les mots inutiles sont ignorés (« *mets-moi* le train », « *s'il te plaît* »).

---

## 2. Train, surfaces, feux

| Phrase | Résultat (F/A-18C) |
|---|---|
| « sors le train », « train d'atterrissage », « je veux sortir le train » | `Maj+G` — train sorti |
| « rentre le train », « range le train » | `Ctrl+G` — train rentré |
| « volets », « montre les volets » | affiche `F` |
| « sors les aérofreins », « rentre les aérofreins » | `Maj+B` / `Ctrl+B` |
| « allume le phare », « phare atterrissage » | `Alt droit+L` |
| « allume les feux », « feux extérieurs » | `L` |
| « montre la crosse », « crosse » | affiche la touche crosse |
| « frein de parking » | poignée de parc/secours |

---

## 3. Armement

| Phrase | Résultat |
|---|---|
| « master arm », « montre le master arm » | affiche la touche |
| « active le master arm », « arme le master arm » | `M` (ARM/SAFE) |
| « armement », « quelle touche pour l'armement » | affiche la commande de tir |
| « largage réservoirs », « jettison » | commande de largage si liée |

---

## 4. Pilote automatique

| Phrase | Effet |
|---|---|
| « pilote auto maintien d'altitude » | maintien d'altitude (interrupteur de l'appareil) |
| « pilote auto maintien d'assiette » | maintien d'assiette, si l'appareil l'a |
| « pilote auto en palier » | retour au vol en palier |
| « pilote auto altitude et cap » | altitude + cap |
| « pilote auto altitude et roulis » | altitude + roulis |
| « pilote auto surcharge / override » | surcharge |
| « pilote auto suivi de route » | suivi de route |
| « débraye le pilote auto », « coupe le pilote auto » | débrayage |
| « pilote automatique » (sans mode) | **il demande lequel** (ne touche à rien) |

Trois niveaux d'exécution, dans cet ordre : **touche** du profil → **commande cockpit**
(interrupteur sans raccourci, numéros device/commande) → **commande simulateur générique**,
alors annoncée comme *non confirmée*. S'il n'y a rien de crédible, il le dit.

---

## 5. F-14 — menu Jester / Iceman

| Phrase | Effet |
|---|---|
| « ouvre le menu Jester », « Jester » | `A` |
| « Jester 3 », « va sur 3 », « choisis l'entrée 5 » | `Ctrl+N` |
| « trois », « numéro 8 » (menu ouvert) | `Ctrl+N` |
| « ferme le menu Jester » | `Maj+A` |
| « Jester radar », « ouvre le menu Jester radar » | ouvre, joue le chemin appris, referme |

Le menu est **contextuel** : les numéros changent selon l'écran. Deux méthodes :

- **apprise** — « Jester apprends radar = 1 3 » : mémorisé par appareil dans
  `jester_menu.json`, rejoué ensuite à chaque « Jester radar » ;
- **à la voix** — tu ouvres le menu, tu lis l'écran, tu dis le numéro.

---

## 6. Mission (outils IA, par la voix)

| Phrase | Outil |
|---|---|
| « fais apparaître deux MiG-29 devant moi à 20 nautiques » | `spawn_aircraft` |
| « mets un SA-10 à 30 nautiques au nord » | `spawn_prefab` |
| « une colonne de chars ennemie à 5 nautiques » | `spawn_prefab` / `spawn_ground` |
| « marque la cible avec de la fumée rouge » | `battlefield_mark` |
| « cercle de 5 nautiques sur mon repère F10 » | `battlefield_mark` |
| « ordonne aux alliés d'engager » | `order_engage` |
| « donne-moi ma position, mon cap, mon altitude » | `get_telemetry` |
| « quelles commandes pour le train ? » | `list_controls` |

---

## 7. Personas (indicatifs)

| Indicatif | Rôle |
|---|---|
| **Ryzen** (défaut) | instructeur / copilote |
| **Overlord** | AWACS, situation tactique |
| **IceMan** | ailier |

Adressage : commence la phrase par l'indicatif (« Overlord, picture »). Sans indicatif,
c'est le persona actif qui répond. Chaque persona a sa langue et sa voix.

---

## 8. Ce qu'il ne fait pas

- Il **ne clique pas** dans un cockpit sans numéros valides ni raccourci : dans ce cas il
  explique où se trouve l'interrupteur et propose de le lier dans *Options > Commandes*.
- Il **n'envoie jamais** de touches si DCS n'est pas au premier plan.
- Il **n'invente pas** une commande : s'il ne la connaît pas, il le dit et propose les
  plus proches.
