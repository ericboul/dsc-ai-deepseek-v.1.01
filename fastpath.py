"""Commandes vocales déterministes — sans LLM.

Pourquoi : un petit modèle local (4B sur NPU) se trompe sur les ARGUMENTS des
outils (il a répondu `press_control(control="TRN OUT")` au lieu de « train »).
Les commandes de l'avion, elles, sont reconnaissables de façon fiable : on les
traite ici, en local, en quelques millisecondes, et on ne laisse au LLM que la
conversation et l'instruction.

    detect("sors le train")        -> {"action": "press", "query": "sors le train"}
    detect("montre-moi les volets")-> {"action": "show",  ...}
    detect("pilote auto altitude") -> {"action": "autopilot", "mode": "alt_hold"}
    detect("quoi de neuf ?")       -> None  (-> au LLM)
"""
import re

import dcs_keys

# verbes qui demandent une EXÉCUTION
PRESS_VERBS = (
    "mets", "met", "mettez", "mettre", "sors", "sortir", "sortez", "sort",
    "rentre", "rentrer", "rentrez", "range", "ranger", "remonte", "remonter",
    "active", "activer", "activez", "arme", "armer", "armez", "desarme",
    "desarmer", "ouvre", "ouvrir", "ouvrez", "ferme", "fermer", "fermez",
    "deploie", "deployer", "deployez", "etends", "etendre", "baisse",
    "baisser", "leve", "lever", "coupe", "couper", "coupez", "allume",
    "allumer", "allumez", "eteins", "eteindre", "lance", "lancer", "lancez",
    "abaisse", "abaisser", "bascule", "basculer", "basculez", "tire", "tirer",
    "largue", "larguer", "enclenche", "enclencher", "debraye", "debrayer",
    "desengage", "desengager", "engage", "engager", "pousse", "pousser",
)
# verbes qui demandent seulement un AFFICHAGE
SHOW_VERBS = (
    "montre", "montrer", "montrez", "affiche", "afficher", "affichez",
    "indique", "indiquer", "rappelle", "rappeler", "ou est", "ou se trouve",
    "c est quoi", "comment on", "comment faire", "quelle touche", "quel bouton",
    "explique", "expliquer",
)
AP_WORDS = ("pilote auto", "pilote automatique", "autopilote", "afcs",
            "pa ", " pa", "stabilise", "maintiens", "maintenez", "maintien")

# mode d'autopilote -> mots déclencheurs (ordre = priorité)
AP_TRIGGERS = (
    ("alt_hdg", ("altitude et cap", "altitude cap", "cap et altitude")),
    ("alt_bank", ("altitude et roulis", "altitude roulis")),
    ("alt_hold", ("maintien d altitude", "maintien altitude", "maintiens l altitude",
                  "maintien alt", "alt hold", "tenir l altitude", "garde l altitude",
                  "altitude hold", "stab altitude")),
    ("att_hold", ("maintien d assiette", "maintien assiette", "attitude",
                  "assiette", "att hold")),
    ("level", ("palier", "niveau", "vol horizontal", "remets a plat", "level")),
    ("route", ("suivi de route", "suivre la route", "route")),
    ("override", ("override", "surcharge")),
    ("off", ("debraye", "debrayer", "coupe le pilote", "desengage", "off",
             "desactive le pilote", "rends moi le controle")),
)

_ACTION_WORDS = set()
for _v in PRESS_VERBS + SHOW_VERBS:
    _ACTION_WORDS.update(_v.split())

# mots à retirer avant de chercher la commande (« sors LE train » -> « train »)
_FILLERS = {"le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "au",
            "aux", "mon", "ma", "mes", "ton", "ta", "tes", "moi", "toi", "s",
            "il", "te", "plait", "stp", "svp", "please", "maintenant", "vite",
            "donc", "et", "un", "peu", "s il", "te", "faut", "je", "tu", "on",
            "veux", "peux", "pourrais", "voudrais", "encore", "aussi", "bien",
            "ou", "sont", "est", "quel", "quelle", "quels", "quelles", "comment",
            "pourquoi", "quand", "s il", "te", "plait", "svp", "pour", "dans",
            "sur", "sous", "avec", "sans", "vers", "a", "par", "au", "aux", "en",
            "y", "s", "qu", "c", "n", "d", "j", "m", "t", "l"}


_META = {"touche", "touches", "bouton", "boutons", "commande", "commandes",
         "raccourci", "raccourcis", "touche-la", "affichage"}


def core_query(text):
    """Phrase débarrassée des verbes d'action et des mots de remplissage."""
    words = dcs_keys.norm(text).split()
    keep = [w for w in words
            if w not in _ACTION_WORDS and w not in _FILLERS and w not in _META]
    return " ".join(keep)


def _has(words, text):
    return any(re.search(r"(^|\s)" + re.escape(w) + r"(\s|$)", text) for w in words)


def _ap_mode(text):
    """Mode d'autopilote demandé, ou None."""
    if not any(w.strip() in text for w in AP_WORDS) and "pilote" not in text:
        return None
    for mode, trigs in AP_TRIGGERS:
        if any(t in text for t in trigs):
            return mode
    return None


JESTER_WORDS = ("jester", "iceman", "ice man", "menu jester", "menu iceman")


_JESTER_CACHE = {}


def has_jester_menu(aircraft):
    """True si l'appareil a bien un menu Jester/Iceman (F-14)."""
    if aircraft in _JESTER_CACHE:
        return _JESTER_CACHE[aircraft]
    ok = False
    try:
        row = dcs_keys.resolve("toggle menu", aircraft, "fr")
        cat = dcs_keys.norm((row or {}).get("category", ""))
        ok = bool(row) and ("jester" in cat or "iceman" in cat)
    except Exception:
        ok = False
    _JESTER_CACHE[aircraft] = ok
    return ok


_STRIP = ("ouvre", "ouvrir", "affiche", "afficher", "montre", "ferme", "fermer",
          "va", "vas", "sur", "passe", "choisis", "selectionne", "prends", "met",
          "mets", "en", "mode", "le", "la", "les", "du", "de", "menu", "jester",
          "iceman", "ice", "man", "numero", "entree", "item", "option")


def _strip_words(t):
    for w in _STRIP:
        t = re.sub(r"(^|\s)" + re.escape(w) + r"(\s|$)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def detect_jester(text, aircraft=None):
    """Intentions liées au menu Jester / Iceman du F-14."""
    t = dcs_keys.norm(text)
    if not t:
        return None
    explicit = any(w in t for w in ("jester", "iceman", "ice man"))
    if not explicit:
        # hors mot « jester/iceman », seul « menu » + verbe explicite compte
        if not ("menu" in t and any(v in t for v in
                                    ("ouvre", "ouvrir", "ferme", "fermer", "affiche"))):
            return None

    # fermer
    if any(v in t for v in ("ferme", "fermer", "quitte", "close")):
        return {"action": "jester", "mode": "close", "query": text}

    # choisir une entrée numérotée
    m = re.search(r"(?:jester|iceman|entree|numero|option)?\s*([1-8])\b", t)
    if m and not any(v in t for v in ("ouvre", "ouvrir", "affiche", "montre")):
        # un numéro cité AVEC le mot jester = choix d'entrée
        if len(re.findall(r"\b[1-8]\b", t)) and re.search(r"\b[1-8]\b", t):
            return {"action": "jester", "mode": "item", "n": int(m.group(1)), "query": text}

    # ouvrir (et éventuellement aller sur un sous-menu nommé)
    rest = _strip_words(t)
    if any(v in t for v in ("ouvre", "ouvrir", "affiche", "montre")):
        if rest:
            return {"action": "jester", "mode": "named", "name": rest, "query": text}
        return {"action": "jester", "mode": "open", "query": text}

    # « jester radar air air » / « va sur radar » -> nom
    if rest:
        return {"action": "jester", "mode": "named", "name": rest, "query": text}
    return {"action": "jester", "mode": "open", "query": text}


def detect_number(text):
    """« trois », « 3 », « va sur 3 » -> 3 (menu Jester ouvert)."""
    t = dcs_keys.norm(text)
    for w in ("va", "vas", "sur", "passe", "choisis", "selectionne", "prends", "met",
              "mets", "le", "la", "les", "l", "du", "de", "en", "mode", "option",
              "item", "entree", "numero", "jester", "iceman"):
        t = re.sub(r"(^|\s)" + re.escape(w) + r"(\s|$)", " ", t)
    words = {"un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
             "six": 6, "sept": 7, "huit": 8}
    t = re.sub(r"(^|\s)(numero|numéro|entree|entrée|l|le|la)(\s|$)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if t in words:
        return words[t]
    if re.fullmatch(r"[1-8]", t):
        return int(t)
    return None


def detect(text, aircraft=None, lang="fr", min_score=55):
    """Analyse une phrase prononcée. Renvoie une intention, ou None si ce n'est
    pas une commande d'avion (à laisser au LLM)."""
    raw = (text or "").strip()
    if not raw:
        return None
    t = dcs_keys.norm(raw)
    if not t:
        return None

    # 0) menu Jester / Iceman (F-14) : à traiter avant les commandes
    j = detect_jester(raw, aircraft)
    if j:
        return j

    # 1) autopilote (avant tout : « mets le pilote auto en maintien d'altitude »)
    if "pilote" in t or any(w.strip() in t for w in AP_WORDS):
        mode = _ap_mode(t)
        if mode:
            return {"action": "autopilot", "mode": mode, "query": raw}
        if "pilote" in t or "autopilote" in t:
            # pas de mode précisé : on demande plutôt que d'appuyer au hasard
            # (sur le Hornet, « pilote automatique » seul = palette de coupure)
            return {"action": "autopilot", "mode": None, "query": raw}

    # 2) intention : montrer ou exécuter
    show = _has(SHOW_VERBS, t)
    press = _has(PRESS_VERBS, t)
    if show and not press:
        action = "show"
    elif press:
        action = "press"
    elif show:
        action = "show"
    else:
        # pas de verbe : une phrase très courte qui EST un nom de commande
        # (« les volets », « train ») -> on montre plutôt que d'exécuter.
        if len(t.split()) > 4:
            return None
        action = "show"

    # 3) la commande existe-t-elle, sans ambiguïté ?
    query = core_query(raw) or raw
    hits = dcs_keys.search(query, aircraft, lang, limit=2)
    if not hits:
        return None
    weights = dcs_keys._weights(dcs_keys.catalog(aircraft, lang), (aircraft, lang))
    s1 = dcs_keys.score_row(hits[0], query, weights)
    s2 = dcs_keys.score_row(hits[1], query, weights) if len(hits) > 1 else 0
    # Tous les mots utiles doivent figurer TELLES QUELLES dans le libellé :
    # « cible » ne doit pas désigner « désignation de ciblage » (préfixe).
    text_words = dcs_keys._row_text(hits[0]).split()
    core_words = [w for w in dcs_keys.norm(query).split() if len(w) >= 3]
    kept = [w for w in core_words if w in text_words]
    # tolérance : un qualificatif en trop (« phare ATTERRISSAGE ») est ignoré,
    # mais il doit rester au moins un mot réellement présent dans le libellé.
    if not kept or len(kept) < min(len(core_words), len(core_words) - 1):
        return None
    if action == "show" and not any(w in t for w in ("touche", "bouton", "commande")):
        min_score = max(min_score, 60)
    if s1 < min_score:
        return None
    if s1 - s2 < 4 and norm_key(hits[0]) == norm_key(hits[1]):
        # deux variantes strictement équivalentes (ex. UP/DOWN) : on ne devine pas
        return None
    return {"action": action, "query": raw, "core": query, "row": hits[0],
            "score": round(s1), "alternatives": [h.get("label") for h in hits[1:]]}


def norm_key(row):
    return dcs_keys.norm((row or {}).get("label", ""))


def short_label(label, limit=48):
    """Libellé utilisable à l'oral : on coupe aux précisions techniques."""
    lab = (label or "").split(" - ")[0].split(" (")[0].strip()
    lab = re.sub(r"\s+", " ", lab)
    return lab[:limit]


def reply(intent, result):
    """Phrase brève de retour, style radio (pas de LLM)."""
    if not intent:
        return ""
    if intent["action"] == "jester":
        if result.get("demande_numero"):
            return "Menu Jester ouvert, dis le numéro."
        if intent.get("mode") == "open":
            return "Menu Jester ouvert."
        if intent.get("mode") == "close":
            return "Menu Jester fermé."
        if result.get("ok"):
            lab = "Entrée %s" % intent.get("n") if intent.get("n") else (intent.get("name") or "Jester")
            return "%s, fait." % lab
        return "Jester : %s" % (result.get("error") or "échec")
    if intent["action"] == "autopilot":
        if result.get("ok"):
            return "%s, engagé." % short_label(result.get("label", "pilote auto"))
        return "Pilote auto : %s" % (result.get("error") or "échec")
    lab = short_label(result.get("label") or (intent.get("row") or {}).get("label", ""))
    combo = result.get("touche") or ""
    if result.get("ok"):
        if intent["action"] == "show":
            return "%s. Touche %s." % (lab, combo) if combo else "%s. Pas de touche." % lab
        return "%s. %s." % (lab, combo) if combo else "%s, fait." % lab
    err = result.get("error") or "échec"
    if "introuvable" in err:
        return "%s : commande introuvable." % (lab or "?")
    return "%s. %s" % (lab or "?", err)


def candidates(text, aircraft=None, lang="fr", limit=4):
    """Libellés proches (pour aider le LLM quand le mode rapide n'a pas tranché)."""
    out = []
    for r in dcs_keys.search(text, aircraft, lang, limit=limit):
        out.append({"label": r.get("label"), "touche": dcs_keys.combo_label(r)})
    return out
