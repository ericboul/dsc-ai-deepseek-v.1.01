"""Catalogue des commandes cockpit DCS, en français, avec leur touche.

Lit les profils d'entrée livrés avec DCS (clavier commun + clavier de
l'appareil) et les affectations du joueur (HOTAS .diff.lua), puis les traduit
avec les fichiers gettext de DCS (l10n/fr/LC_MESSAGES/input.mo) : le copilote
parle donc avec EXACTEMENT les libellés que DCS affiche.

Aucune dépendance externe : uniquement la bibliothèque standard.
"""
import gettext
import glob
import os
import re
import unicodedata

# --------------------------------------------------------------------------
# Emplacements
# --------------------------------------------------------------------------
_DCS_CANDIDATES = [
    r"C:\Program Files\Eagle Dynamics\DCS World",
    r"C:\Program Files (x86)\Eagle Dynamics\DCS World",
    r"D:\Eagle Dynamics\DCS World",
    r"E:\Eagle Dynamics\DCS World",
]


def dcs_install(override=None):
    """Racine de DCS World (détectée, ou forcée par la config)."""
    if override and os.path.isdir(override):
        return override
    env = os.environ.get("DCS_INSTALL")
    if env and os.path.isdir(env):
        return env
    for c in _DCS_CANDIDATES:
        if os.path.isdir(os.path.join(c, "Scripts")):
            return c
    for pat in (r"C:\Program Files\Eagle Dynamics\*",
                r"C:\Program Files (x86)\Eagle Dynamics\*",
                r"D:\*\DCS World", r"E:\*\DCS World"):
        for p in glob.glob(pat):
            if os.path.isdir(os.path.join(p, "Scripts")):
                return p
    return None


def saved_games(override=None):
    """Dossier « Saved Games/DCS » du joueur (profils et hooks)."""
    if override and os.path.isdir(override):
        return override
    env = os.environ.get("DCS_SAVED_GAMES")
    if env and os.path.isdir(env):
        return env
    base = os.path.join(os.path.expanduser("~"), "Saved Games")
    for name in ("DCS", "DCS.openbeta", "DCS.openbeta_server", "DCS_server"):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    return os.path.join(base, "DCS")


# --------------------------------------------------------------------------
# Outils texte
# --------------------------------------------------------------------------
def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


def norm(s):
    """Minuscule, sans accents, ponctuation -> espaces (pour comparer)."""
    s = _strip_accents(str(s or "")).lower()
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Mots vides : ils polluent la comparaison (« mets le train »).
_STOP = {
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "au", "aux",
    "mon", "ma", "mes", "ton", "ta", "tes", "ce", "cette", "il", "elle", "je",
    "tu", "on", "nous", "vous", "moi", "toi", "s", "se", "sur", "sous", "dans",
    "en", "a", "et", "ou", "pour", "avec", "par", "est", "sont", "the", "of",
    "mets", "met", "mettre", "mise", "passe", "passer", "appuie", "appuyer",
    "presse", "presser", "donne", "donner", "montre", "montrer", "affiche",
    "afficher", "active", "activer", "arme", "armer", "desactive", "coupe",
    "couper", "ouvre", "ouvrir", "ferme", "fermer", "fais", "faire", "peux",
    "veux", "commande", "commander", "maintenant", "stp", "svp", "please",
}


def tokens(s):
    return [w for w in norm(s).split() if w not in _STOP and len(w) > 1]


# --------------------------------------------------------------------------
# Dictionnaire de synonymes FR -> vocabulaire des libellés DCS (anglais)
# --------------------------------------------------------------------------
# Le libellé DCS est en anglais dans les .lua ; la traduction FR vient de
# input.mo. Ce tableau sert de filet quand un libellé n'est pas traduit, et
# pour comprendre les formulations du pilote (« rentre le train »).
SYNONYMS = {
    # train / atterrissage
    "train": ["gear", "landing gear"],
    "atterrissage": ["landing", "gear"],
    "atterrisseur": ["gear"],
    "roulette": ["wheel", "nosewheel"],
    "crosse": ["hook", "arresting"],
    "crochet": ["hook", "arresting"],
    "catapulte": ["catapult", "launch bar", "launchbar"],
    "bride": ["launch bar", "launchbar"],
    # surfaces
    "volets": ["flap", "flaps"],
    "aero frein": ["speed brake", "speedbrake", "airbrake"],
    "aerofrein": ["speed brake", "speedbrake", "airbrake"],
    "frein aerodynamique": ["speed brake", "speedbrake"],
    "frein de parking": ["parking brake", "park brake"],
    "frein": ["brake"],
    "compensation": ["trim"],
    "assiette": ["pitch", "attitude"],
    # autopilote
    "pilote automatique": ["autopilot", "afcs", "ap"],
    "pa": ["autopilot", "afcs"],
    "maintien altitude": ["alt hold", "altitude hold", "altitude"],
    "altitude": ["altitude", "alt"],
    "maintien cap": ["hsel", "heading select", "heading"],
    "cap": ["heading", "hsel"],
    "navigation": ["nav", "navigation"],
    "approche": ["app", "approach"],
    "palier": ["level", "att hold", "attitude hold"],
    "asservissement": ["autopilot", "afcs"],
    # armement
    "armement": ["master arm", "armament", "weapon"],
    "armement maitre": ["master arm"],
    "master arm": ["master arm"],
    "securite": ["safe", "safety"],
    "canon": ["gun"],
    "mitrailleuse": ["gun", "machine gun"],
    "missile": ["missile", "aam"],
    "bombe": ["bomb"],
    "roquette": ["rocket"],
    "largage": ["release", "pickle", "weapon release"],
    "tir": ["trigger", "fire"],
    "gachette": ["trigger"],
    "selection arme": ["weapon select"],
    # contre-mesures
    "contre mesures": ["countermeasure", "dispenser", "cms"],
    "leurres": ["flare"],
    "fusee": ["flare"],
    "paillettes": ["chaff"],
    "brouillage": ["jammer", "ecm"],
    "alerte radar": ["rwr"],
    # systèmes
    "feux": ["light", "lights", "exterior"],
    "lumiere": ["light"],
    "phares": ["light", "landing light"],
    "feu de navigation": ["nav light", "position light"],
    "feu anti collision": ["anti collision", "strobe"],
    "batterie": ["battery"],
    "generateur": ["generator"],
    "moteur": ["engine"],
    "demarrage": ["start", "crank"],
    "carburant": ["fuel"],
    "ravitaillement": ["refuel", "aerial refuel", "probe"],
    "perche": ["probe", "refuel"],
    "oxygene": ["oxygen", "obogs"],
    "pressurisation": ["pressurization", "cabin pressure"],
    "verriere": ["canopy"],
    "cockpit": ["canopy", "cockpit"],
    "siege ejection": ["eject", "ejection seat"],
    "ejection": ["eject"],
    "train avant": ["nose gear", "nosewheel"],
    "radio": ["radio", "comm"],
    "frequence": ["frequency", "freq"],
    "transpondeur": ["iff", "transponder"],
    "tacan": ["tacan"],
    "ils": ["ils"],
    "radar": ["radar", "rws"],
    "mode radar": ["radar mode"],
    "mfd": ["mfd", "display"],
    "ecran": ["display", "mfd"],
    "hud": ["hud"],
    "nacelle": ["pod", "targeting"],
    "pods": ["pod"],
    "armement sol": ["air ground", "a g"],
    "vol stationnaire": ["hover"],
    "pas collectif": ["collective"],
    "cyclique": ["cyclic"],
    "roulis": ["roll"],
    "tangage": ["pitch"],
    "lacet": ["yaw"],
    "palonnier": ["rudder"],
    "directeur de vol": ["flight director", "fdir"],
    "transparence": ["hud"],
    "soute": ["bay", "doors"],
    "trappe": ["door", "bay"],
    "aile": ["wing", "fold"],
    "repli": ["fold"],
    "crochet d arret": ["arresting hook"],
    "barre de lancement": ["launch bar"],
    "antipatinage": ["anti skid", "antiskid"],
    "phare": ["phare", "light", "landing light"],
    "phares": ["phare", "light", "landing light"],
    "phare d atterrissage": ["phare", "landing light", "taxi light"],
    "phare atterrissage": ["phare", "landing light", "taxi light"],
    "feux atterrissage": ["phare", "landing light", "taxi light"],
    "phare de train": ["phare", "landing light"],
    "feux d atterrissage": ["phare", "landing light"],
    "maintien d altitude": ["alt hold", "altitude hold", "altitude"],
    "pilote auto": ["autopilot", "afcs"],
    "autopilote": ["autopilot", "afcs"],
    "pompe": ["pump"],
    "circuit hydraulique": ["hydraulic"],
    "pression": ["pressure"],
    "eclairage": ["lighting", "light"],
    "instrument": ["instrument"],
}

# Préférences directionnelles : « rentre » -> UP/RETRACT, « sors » -> DOWN/EXTEND
_UP_WORDS = ["up", "retract", "on", "in", "close", "stow", "raise", "rétraction",
             "retraction", "armer", "arm"]
_DOWN_WORDS = ["down", "extend", "off", "out", "open", "deploy", "lower",
               "extension", "desarmer", "disarm", "safe"]
_DIR_UP = {"rentre", "rentrer", "remonte", "remonter", "range", "ranger",
           "replie", "replier", "monte", "monter", "leve", "lever",
           "retracte", "retracter", "ferme", "fermer", "coupe", "couper",
           "desarme", "desarmer", "eteins", "eteindre", "off", "arret"}
_DIR_DOWN = {"sors", "sortir", "descend", "descendre", "baisse", "baisser",
             "etend", "etendre", "deploie", "deployer", "ouvre", "ouvrir",
             "abaisse", "abaisser", "arme", "armer", "allume", "allumer",
             "on", "marche", "extend", "down"}


# --------------------------------------------------------------------------
# Analyse des fichiers de profil Lua (sans interpréteur Lua)
# --------------------------------------------------------------------------
def _strip_lua_comments(text):
    """Vide les commentaires Lua (même longueur) pour ne pas casser le comptage
    d'accolades : les profils DCS en contiennent des centaines."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            q = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            # commentaire de ligne, ou bloc --[[ ... ]]
            j = i + 2
            if text.startswith("[[", j):
                end = text.find("]]", j + 2)
                end = n if end < 0 else end + 2
            else:
                end = text.find("\n", j)
                end = n if end < 0 else end
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def _blocks(text):
    """Rend (start, end) de chaque paire d'accolades équilibrée du texte,
    en ignorant les accolades situées dans des chaînes Lua."""
    out = []
    stack = []
    in_str = None
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
        elif ch in "'\"":
            in_str = ch
        elif ch == "{":
            stack.append(i)
        elif ch == "}":
            if stack:
                out.append((stack.pop(), i))
    return out


def _unesc(s):
    return (s or "").replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


_NAME_KV = re.compile(r"""\bname\s*=\s*(?:_\(\s*)?'((?:[^'\\]|\\.)*)'""")
_NAME_KV2 = re.compile(r'\["name"\]\s*=\s*"((?:[^"\\]|\\.)*)"')
_KEY_KV = re.compile(r"""\bkey\s*=\s*'([^']*)'""")
_KEY_KV2 = re.compile(r'\["key"\]\s*=\s*"([^"]*)"')
_REFORMERS = re.compile(r"reformers\s*=\s*\{([^}]*)\}")
_DEV = re.compile(r"cockpit_device_id\s*=\s*([A-Za-z0-9_.]+)")
_RE_DOWN = re.compile(r"\bdown\s*=\s*([A-Za-z0-9_.]+)")
_RE_UP = re.compile(r"\bup\s*=\s*([A-Za-z0-9_.]+)")
_VDOWN = re.compile(r"value_down\s*=\s*(-?[0-9.]+)")
_VUP = re.compile(r"value_up\s*=\s*(-?[0-9.]+)")
_CAT = re.compile(r"""category\s*=\s*\{?\s*_\(\s*'([^']*)'""")
_DIFFID = re.compile(r'\["(d[0-9a-z_]+)"\]')


def _parse_commands_lua(text):
    """Extrait les entrées {combos=…, down=…, name=…} d'un profil DCS."""
    text = _strip_lua_comments(text)
    rows = []
    for s, e in _blocks(text):
        body = text[s:e + 1]
        if "name" not in body or ("combos" not in body and "down" not in body):
            continue
        m = _NAME_KV.search(body)
        if not m:
            continue
        km = _KEY_KV.search(body)
        rm = _REFORMERS.search(body)
        cat = _CAT.search(body)
        dm = _DEV.search(body)
        dn = _RE_DOWN.search(body)
        up = _RE_UP.search(body)
        vd = _VDOWN.search(body)
        vu = _VUP.search(body)
        rows.append({
            "name": _unesc(m.group(1)),
            "key": km.group(1) if km else None,
            "mods": re.findall(r"'([^']+)'", rm.group(1)) if rm else [],
            "device": dm.group(1) if dm else None,
            "command": dn.group(1) if dn else None,
            "up": up.group(1) if up else None,
            "value": float(vd.group(1)) if vd else None,
            "value_up": float(vu.group(1)) if vu else None,
            "category": cat.group(1) if cat else "",
            "source": "keyboard",
        })
    return rows


def _parse_diff_lua(text, origin):
    """Extrait les affectations ajoutées par le joueur (fichiers .diff.lua)."""
    raw = text
    text = _strip_lua_comments(text)
    rows = []
    for s, e in _blocks(text):
        body = text[s:e + 1]
        m = _NAME_KV2.search(body)
        if not m or "added" not in body:
            continue
        keys = _KEY_KV2.findall(body)
        if not keys:
            continue
        pre = text[max(0, s - 260):s]
        ids = _DIFFID.findall(pre)
        dev = cmd = None
        if ids:
            did = ids[-1]
            d1 = re.match(r"d(\d+)", did)
            d2 = re.search(r"cd(\d+)", did)
            vd = re.search(r"vd(-?[0-9.]+)", did)
            dev = d2.group(1) if d2 else None
            cmd = d1.group(1) if d1 else None
            val = float(vd.group(1)) if vd else None
        else:
            val = None
        rows.append({
            "name": _unesc(m.group(1)),
            "key": keys[0],
            "mods": [],
            "device": dev, "command": cmd, "value": val, "value_up": None,
            "category": "", "source": origin,
        })
    return rows


# --------------------------------------------------------------------------
# Traductions DCS (gettext)
# --------------------------------------------------------------------------
_TR_CACHE = {}


def translations(lang="fr", root=None):
    """Table msgid anglais -> libellé traduit, tirée des .mo de DCS."""
    lang = (lang or "fr")[:2].lower()
    if lang == "en":
        return {}
    if lang in _TR_CACHE:
        return _TR_CACHE[lang]
    table = {}
    root = root or dcs_install()
    if root:
        for mo in (os.path.join(root, "l10n", lang, "LC_MESSAGES", "input.mo"),
                   os.path.join(root, "l10n", lang, "LC_MESSAGES", "dcs.mo"),
                   os.path.join(root, "l10n", lang, "LC_MESSAGES", "about.mo")):
            try:
                with open(mo, "rb") as f:
                    cat = gettext.GNUTranslations(f)._catalog
            except Exception:
                continue
            for k, v in cat.items():
                if isinstance(k, str) and isinstance(v, str) and k and v:
                    table.setdefault(k, v)
    _TR_CACHE[lang] = table
    return table


# --------------------------------------------------------------------------
# Modules / profils d'appareil
# --------------------------------------------------------------------------
def _module_roots(root):
    return [os.path.join(root, "Mods", "aircraft"),
            os.path.join(root, "CoreMods", "aircraft"),
            os.path.join(root, "Mods", "tech"),
            os.path.join(root, "CoreMods", "tech")]


def _profiles(module_dir):
    """Liste (nom_profil, dossier) des profils d'entrée d'un module."""
    inp = os.path.join(module_dir, "Input")
    out = []
    if os.path.isdir(inp):
        for name in os.listdir(inp):
            p = os.path.join(inp, name)
            if os.path.isdir(p):
                out.append((name, p))
    return out


def find_aircraft(aircraft_type, root=None):
    """Trouve (module_dir, profile_name, input_dir) pour un type DCS.

    Ex. 'FA-18C_hornet' -> (…/Mods/aircraft/FA-18C, 'FA-18C', …).
    """
    root = root or dcs_install()
    if not root:
        return None
    t = norm(aircraft_type)
    if not t:
        return None
    best = None
    for base in _module_roots(root):
        if not os.path.isdir(base):
            continue
        for module in os.listdir(base):
            mdir = os.path.join(base, module)
            if not os.path.isdir(mdir):
                continue
            profs = _profiles(mdir)
            if not profs:
                continue
            mn = norm(module)
            score = 0
            if mn and (mn in t or t in mn):
                score = 50 + min(len(mn), 20)
            for pname, pdir in profs:
                pn = norm(pname)
                if not pn:
                    continue
                if pn == t:
                    score = max(score, 100)
                elif pn in t or t in pn:
                    score = max(score, 60 + min(len(pn), 20))
            if score and (best is None or score > best[0]):
                best = (score, mdir, profs[0][0], profs[0][1])
    if not best:
        return None
    # profil le mieux aligné sur le type
    _, mdir, _, _ = best
    profs = _profiles(mdir)
    chosen = profs[0]
    for pname, pdir in profs:
        if norm(pname) == t:
            chosen = (pname, pdir)
            break
    return mdir, chosen[0], chosen[1]


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------
_CAT_CACHE = {}


def catalog(aircraft_type=None, lang="fr", root=None, saved=None):
    """Liste des commandes connues pour cet appareil (clavier + HOTAS + commun).

    Chaque entrée : name (anglais), label (traduit), key, mods, combo,
    source ('keyboard' | 'hotas' | 'common'), category.
    """
    root = root or dcs_install()
    saved = saved or saved_games()
    key = (aircraft_type, lang, root, saved)
    if key in _CAT_CACHE:
        return _CAT_CACHE[key]

    rows = []
    if root:
        # 1) liaisons communes à tous les appareils
        for name in ("base_keyboard_binding.lua", "common_keyboard_binding.lua"):
            p = os.path.join(root, "Config", "Input", "Aircrafts", name)
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for r in _parse_commands_lua(f.read()):
                            r["source"] = "common"
                            rows.append(r)
                except Exception:
                    pass

        # 2) clavier de l'appareil
        found = find_aircraft(aircraft_type, root) if aircraft_type else None
        if found:
            _, pname, pdir = found
            for p in glob.glob(os.path.join(pdir, "keyboard", "*.lua")):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        rows.extend(_parse_commands_lua(f.read()))
                except Exception:
                    pass
            # 3) affectations du joueur : clavier puis HOTAS
            if saved:
                ubase = os.path.join(saved, "Config", "Input")
                for cand in (pname, aircraft_type):
                    if not cand:
                        continue
                    udir = os.path.join(ubase, cand)
                    if not os.path.isdir(udir):
                        continue
                    for p in glob.glob(os.path.join(udir, "keyboard", "*.lua")):
                        try:
                            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                rows.extend(_parse_commands_lua(f.read()))
                        except Exception:
                            pass
                    for p in glob.glob(os.path.join(udir, "joystick", "*.diff.lua")):
                        try:
                            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                rows.extend(_parse_diff_lua(f.read(), "hotas"))
                        except Exception:
                            pass

    tr = translations(lang, root)
    seen = set()
    out = []
    for r in rows:
        label = tr.get(r["name"], r["name"])
        r["label"] = label
        sig = (norm(label), r.get("key"))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(r)
    _CAT_CACHE[key] = out
    return out


def combo_label(row):
    """« Ctrl+Maj+G » lisible (pour l'affichage et la voix)."""
    mods = row.get("mods") or []
    pretty = []
    for m in mods:
        ml = m.lower()
        if "ctrl" in ml:
            pretty.append("Ctrl droit" if ml.startswith("r") else "Ctrl")
        elif "shift" in ml:
            pretty.append("Maj droite" if ml.startswith("r") else "Maj")
        elif "alt" in ml:
            pretty.append("Alt droit" if ml.startswith("r") else "Alt")
        elif "win" in ml:
            pretty.append("Win")
        else:
            pretty.append(m)
    k = row.get("key") or ""
    if k.startswith("JOY_BTN"):
        try:
            k = "HOTAS bouton %d" % (int(k[7:]) + 1)
        except ValueError:
            pass
    return "+".join(pretty + [k]) if k else ""


_NOISE = ("camera", "caméra", "vue ", "view ", "mouse", "souris", "debug",
          "console", "chat", "track replay", "screen shot", "capture")


def _row_text(row):
    return norm(" ".join([row.get("label", ""), row.get("name", ""),
                          row.get("category", "")]))


_W_CACHE = {}


def _weights(rows, cache_key):
    """Poids des mots (les mots rares comptent plus : « phare » > « train »)."""
    if cache_key in _W_CACHE:
        return _W_CACHE[cache_key]
    import math
    df = {}
    n = 0
    for r in rows:
        n += 1
        for w in set(_row_text(r).split()):
            df[w] = df.get(w, 0) + 1
    w = {k: 1.0 + math.log(1.0 + n / (1.0 + v)) for k, v in df.items()}
    _W_CACHE[cache_key] = w
    return w


def _direction_bonus(query_words, text_norm):
    up = any(w in _DIR_UP for w in query_words)
    down = any(w in _DIR_DOWN for w in query_words)
    if not (up or down):
        # pas de direction demandée : on préfère « sortir/étendre » (le geste
        # utile en approche) plutôt que la position inverse, à égalité.
        if any(w in text_norm for w in _DOWN_WORDS):
            return 3
        if any(w in text_norm for w in _UP_WORDS):
            return -3
        return 0
    if up and any(w in text_norm for w in _UP_WORDS):
        return 14
    if down and any(w in text_norm for w in _DOWN_WORDS):
        return 14
    return -8


_SUFFIXES = ("issements", "issement", "ations", "ation", "ements", "ement",
             "erons", "erez", "er", "ez", "es", "ent", "ant", "ee", "e", "s")


def _stem(w):
    """Radical grossier : « maintien/maintien » « altitude/altitudes »."""
    w = w or ""
    if len(w) <= 4:
        return w
    for suf in _SUFFIXES:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _word_hit(word, text, text_words):
    """1.0 si le mot est présent (exact ou même radical), 0 sinon."""
    if word in text_words:
        return 1.0
    st = _stem(word)
    for tw in text_words:
        if tw == word or _stem(tw) == st:
            return 0.9
        if len(word) >= 4 and len(tw) >= 4 and (
                tw.startswith(word) or word.startswith(tw)):
            return 0.6
    return 0.0


def score_row(row, query, weights=None):
    """Pertinence d'une entrée pour une demande en français (ou anglais)."""
    q = norm(query)
    if not q:
        return 0
    words = tokens(query)
    if not words:
        return 0
    text = _row_text(row)
    if not text:
        return 0
    text_words = text.split()
    s = 0.0
    if norm(row.get("label", "")) == q or norm(row.get("name", "")) == q:
        s += 100
    hits = 0.0
    for w in words:
        hits += _word_hit(w, text, text_words) * (weights.get(w, 3.0) if weights else 3.0)
    s += hits * 3.0
    if all(_word_hit(w, text, text_words) > 0 for w in words):
        s += 30 + min(len(q), 30)
    # synonymes FR -> vocabulaire DCS anglais
    for i in range(len(words)):
        for j in range(i + 2, len(words) + 1):
            term = " ".join(words[i:j])
            syn = SYNONYMS.get(term)
            if syn and any(t in text for t in syn):
                s += 20
    for w in words:
        syn = SYNONYMS.get(w)
        if syn and any(t in text for t in syn):
            s += 10
    # un libellé qui COMMENCE par le mot demandé (« Train d'atterrissage… »
    # pour « train ») est plus probable qu'un libellé qui le contient.
    lab_first = words[0]
    if norm(row.get("label", "")).startswith(lab_first):
        s += 14
    s += _direction_bonus(words, text)
    # bruit (caméras, vues, console de chat...) sauf demande explicite
    if any(nz in text for nz in _NOISE) and not any(nz in q for nz in _NOISE):
        s -= 45
    # une touche clavier existe : plus simple à exécuter/à montrer
    if row.get("key") and not str(row.get("key")).startswith("JOY_BTN"):
        s += 8
    if row.get("source") == "common":
        s -= 4
    return s


def search(query, aircraft_type=None, lang="fr", limit=8):
    """Renvoie les commandes les plus proches de la demande, triées."""
    rows = catalog(aircraft_type, lang)
    weights = _weights(rows, (aircraft_type, lang))
    ql = norm(query)
    explicit_noise = any(nz in ql for nz in _NOISE)
    scored = []
    for r in rows:
        s = score_row(r, query, weights)
        if s <= 0:
            continue
        # les entrées « caméra / vue / chat » ne doivent jamais être proposées
        # pour une commande d'avion (sauf si le pilote parle justement d'elles)
        if not explicit_noise and any(nz in _row_text(r) for nz in _NOISE):
            continue
        scored.append((s, r))
    scored.sort(key=lambda x: (-x[0], 0 if (x[1].get("key") or "").startswith("JOY") else 1))
    return [r for _, r in scored[:limit]]


def resolve(query, aircraft_type=None, lang="fr", min_score=40):
    """Meilleure commande pour la demande, ou None."""
    rows = catalog(aircraft_type, lang)
    weights = _weights(rows, (aircraft_type, lang))
    hits = search(query, aircraft_type, lang, limit=1)
    if not hits:
        return None
    if score_row(hits[0], query, weights) < min_score:
        return None
    return hits[0]


def count(aircraft_type=None, lang="fr"):
    rows = catalog(aircraft_type, lang)
    keys = [r for r in rows if r.get("key") and not str(r["key"]).startswith("JOY_BTN")]
    return {"total": len(rows), "keyboard": len(keys)}
