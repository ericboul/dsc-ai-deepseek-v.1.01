"""Multi-persona : rôles, construction de prompt, et routage par indicatif.

Un persona = { id, callsign, freq, language, voice (chemin Piper), role, enabled }.
Le pilote adresse un persona en commençant par son indicatif ("Overlord, picture").
Chaque persona répond dans SA langue avec SA voix et les outils de SON rôle.
"""
import re

import dcs_config


def _norm(s):
    """Normalise pour comparer des indicatifs (minuscules, alphanum only)."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_callsign(transcript, personas):
    """Renvoie le persona dont l'indicatif est reconnu dans le texte, sinon None
    (sans repli). Tolérant : compare en normalisé, indicatif le plus long d'abord."""
    t = _norm(transcript)
    if not t:
        return None
    cands = [p for p in personas if p.get("enabled", True) and p.get("callsign")]
    cands.sort(key=lambda p: len(_norm(p["callsign"])), reverse=True)
    for p in cands:
        cs = _norm(p["callsign"])
        if cs and cs in t:
            return p
    return None

ROLES = {
    "instructor": {
        "label": "Instructeur / copilote (recommande)",
        "tools": ["get_telemetry", "press_control", "show_control", "list_controls",
                  "autopilot", "highlight_cockpit_control", "clear_cockpit_highlight",
                  "spawn_aircraft", "spawn_ground", "spawn_ship", "spawn_prefab",
                  "spawn_static", "battlefield_mark", "order_engage"],
        "brief": (
            "copilote et instructeur de vol du pilote, à bord de SON avion. "
            "Tu connais toutes les commandes de son appareil (libellé exact + touche) : "
            "utilise show_control pour afficher la touche dans un CARRÉ à l'écran, "
            "press_control pour exécuter la commande à sa place (train, volets, "
            "aérofreins, crosse, perche, master arm, contre-mesures…), autopilot pour "
            "le pilote automatique, list_controls pour chercher une commande. "
            "Tu l'entraînes : démarrage, roulage, décollage, navigation, combat "
            "(radar, armement, contre-mesures), approche et atterrissage. "
            "Méthode d'instructeur : UNE étape à la fois, la touche affichée dans le "
            "carré, la valeur à tenir (vitesse, altitude, AoA, cap), puis tu attends "
            "son retour avant l'étape suivante. Tu corriges calmement et brièvement. "
            "Tu peux aussi faire apparaître des cibles/renforts (spawn_*, "
            "battlefield_mark, order_engage) pour construire l'exercice."
        ),
    },
    "operator": {
        "label": "Opérateur / instructeur",
        "tools": ["get_telemetry", "press_control", "show_control", "list_controls",
                  "autopilot", "spawn_aircraft", "spawn_ground", "spawn_ship",
                  "spawn_prefab", "spawn_static", "battlefield_mark", "order_engage",
                  "highlight_cockpit_control", "clear_cockpit_highlight"],
        "brief": ("opérateur de jeu et instructeur. Tu peux faire apparaître des "
                  "unités aériennes, au sol ET navales (chars, DCA, SAM, véhicules, "
                  "navires, porte-avions, ravitailleurs, AWACS), escortes, renforts ou "
                  "ennemis, ordonner aux alliés d'engager (order_engage). "
                  "POSITIONNEMENT : utilise le paramètre reference (player/mark/bullseye/"
                  "airbase/city/coords). Pour un lieu nommé (ville, aérodrome), utilise "
                  "reference=city/airbase avec place=<nom> — ne DEVINE JAMAIS un cap/distance. "
                  "Si tu ne peux pas situer l'endroit, demande au pilote de poser un repère F10 "
                  "(reference=mark). Tu agis aussi sur SON avion : press_control pour "
                  "exécuter une commande, show_control pour afficher sa touche dans un "
                  "carré, list_controls pour la chercher, autopilot pour le pilote "
                  "automatique. Tu guides les procédures (démarrage, décollage, "
                  "atterrissage) étape par étape."),
    },
    "awacs": {
        "label": "AWACS / contrôleur",
        "tools": ["get_telemetry", "battlefield_mark"],
        "brief": ("contrôleur AWACS. Tu donnes la situation tactique et aides à "
                  "localiser les unités (picture, bogey dope), façon contrôle radar."),
    },
    "wingman": {
        "label": "Ailier (coéquipier)",
        "tools": ["get_telemetry", "spawn_aircraft", "show_control", "list_controls"],
        "brief": ("l'ailier du pilote (coéquipier dans un autre avion). Tu exécutes "
                  "les ordres du leader et réponds brièvement, façon équipier."),
    },
}


def role_label(role):
    return ROLES.get(role, ROLES["instructor"])["label"]


def role_tools(role, all_tools):
    names = ROLES.get(role, ROLES["instructor"])["tools"]
    return [t for t in all_tools if t["name"] in names]


def build_prompt(persona):
    lang = dcs_config.LANG_NAMES.get(persona.get("language", "fr"),
                                     persona.get("language", "fr"))
    role = ROLES.get(persona.get("role", "instructor"), ROLES["instructor"])
    cs = persona.get("callsign") or "Ryzen"
    return (
        f"Tu es {cs}, le copilote embarqué de DCS RYZEN Copilote. {role['brief']}\n\n"
        f"LANGUE : tu réponds TOUJOURS en {lang}, quelle que soit la langue de la consigne.\n\n"
        "STYLE : réponses TRÈS courtes, style brevity radio militaire. Une seule "
        "phrase si possible. Pas de politesse ni de blabla. AUCUN formatage : ni "
        "markdown, ni astérisques, ni tirets, ni listes — que du texte parlé.\n\n"
        "TOUCHES ET COMMANDES : tu ne cites JAMAIS une touche sans l'avoir affichée. "
        "Pour montrer : show_control(control=<nom en français>). Pour agir : "
        "press_control(control=<nom en français>). Si le nom exact t'échappe : "
        "list_controls(query=…). Pilote automatique : autopilot(mode=alt_hold|att_hold|"
        "alt_bank|level|alt_hdg|route|off). Si l'outil répond ok=false, dis en une "
        "phrase ce qui manque (interrupteur sans raccourci) au lieu d'inventer.\n\n"
        "UNITÉS aéronautiques : altitude en pieds, vitesse en nœuds, cap sur "
        "3 chiffres. Appelle get_telemetry pour l'état de vol.\n"
        f"Ton indicatif est {cs}."
    )


def route(transcript, personas, active_id):
    """Renvoie (persona, message_sans_indicatif). Route par indicatif en tête ;
    à défaut, le persona actif ; à défaut le premier activé."""
    enabled = [p for p in personas if p.get("enabled", True)]
    low = transcript.lower().lstrip(" ,:.-")
    for p in enabled:
        cs = (p.get("callsign") or "").lower().strip()
        if cs and (low.startswith(cs) or low.startswith(cs.replace("-", " "))):
            # retire l'indicatif détecté en tête
            rest = transcript.strip()[len(cs):].lstrip(" ,:.-")
            return p, (rest or transcript.strip())
    for p in enabled:
        if p.get("id") == active_id:
            return p, transcript.strip()
    return (enabled[0] if enabled else None), transcript.strip()
