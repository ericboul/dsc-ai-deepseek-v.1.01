"""
DCS RYZEN Copilote — boucle du copilote : push-to-talk -> Whisper -> LLM
(outils DCS) -> voix (Piper/SAPI) + commandes de l'avion (touches + carré à
l'écran) + affichage DCS + radio (SRS).

Toute la config est relue à CHAQUE tour depuis core -> réglages à la volée.
Lancé par app.py (en même temps que l'interface web).
"""
import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import json
import socket
import threading
import time

import numpy as np
import sounddevice as sd

import audioio
import tts
import srs
import core
import personas
import ptt
import fastpath
import jester

UDP_PORT    = 5010            # doit correspondre à dcs_claude_export.lua
SAMPLE_RATE = 16000           # Whisper attend du 16 kHz mono
# NB : le prompt système est construit PAR PERSONA dans personas.build_prompt().


class TelemetryListener:
    """Écoute l'UDP de DCS en thread de fond, garde le dernier état.

    Non bloquant : si le port est déjà pris (deuxième instance du copilote
    lancée par erreur), on continue sans télémétrie au lieu de tuer l'app.
    """
    def __init__(self, port=UDP_PORT):
        self._latest = None
        self._lock = threading.Lock()
        self.ok = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._sock.bind(("127.0.0.1", port))
        except OSError as e:
            print(f"[télémétrie] port UDP {port} déjà utilisé ({e}).")
            print("[télémétrie] Une autre instance du copilote tourne probablement déjà :")
            print("[télémétrie] le copilote démarre SANS télémétrie DCS. Ferme l'autre")
            print("[télémétrie] fenêtre (ou le python.exe en trop) puis relance.")
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
            return
        self._sock.settimeout(0.5)
        self.ok = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        sock = self._sock
        if sock is None:
            return
        while True:
            try:
                data, _ = sock.recvfrom(2048)
                parsed = json.loads(data.decode("utf-8"))
                with self._lock:
                    self._latest = parsed
                    self._latest["_rx_time"] = time.time()
            except socket.timeout:
                continue
            except Exception:
                continue

    def get(self):
        with self._lock:
            return dict(self._latest) if self._latest else None


def _record_active(monitor, device, name=None):
    """Enregistre tant que `monitor` est pressé (sans attente initiale).

    Passe par audioio.open_input_stream : si l'endpoint WASAPI refuse de
    démarrer (casque Bluetooth), l'entrée MME du même micro est essayée.
    """
    frames = []
    stream, used = audioio.open_input_stream(device=device, samplerate=SAMPLE_RATE,
                                             channels=1, name=name)
    if used != device:
        print(f"[micro] {name or device} : repli sur l'index {used}")
    while monitor.pressed:
        data, _ = stream.read(1024)
        frames.append(data.copy())
    stream.stop(); stream.close()
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(frames, axis=0).flatten()


def _wait_any_ptt(global_mon, persona_monitors):
    """Attend qu'un PTT soit pressé. Renvoie (persona_id ou None, monitor)."""
    while True:
        if global_mon.pressed:
            return None, global_mon
        for pid, m in persona_monitors.items():
            if m.pressed:
                return pid, m
        time.sleep(0.01)


def _parse_freq(s):
    try:
        return float(str(s).replace(",", "."))
    except Exception:
        return None


def _select_persona(cfg, ptt_pid, transcript, control, aircraft):
    """Choisit le persona : PTT explicite > fréquence > indicatif > actif.
    Respecte freq_required (si vrai, seule la fréquence/PTT joint un persona)."""
    enabled = [p for p in cfg.get("personas", []) if p.get("enabled", True)]
    if not enabled:
        return None, transcript
    # 1) PTT par persona
    if ptt_pid:
        for p in enabled:
            if p["id"] == ptt_pid:
                return p, transcript
    # 2) Fréquence (F/A-18C uniquement)
    freqp = None
    if control and hasattr(control, "get_frequency") and aircraft == "FA-18C_hornet":
        f1 = control.get_frequency(38)
        f2 = control.get_frequency(39)
        for p in enabled:
            pf = _parse_freq(p.get("freq"))
            if pf and ((f1 and abs(f1 - pf) < 0.05) or (f2 and abs(f2 - pf) < 0.05)):
                freqp = p
                break
    if freqp:
        return freqp, transcript
    if cfg.get("freq_required"):
        return None, transcript   # doit être sur une fréquence connue
    # 3) Indicatif parlé
    m = personas.match_callsign(transcript, enabled)
    if m:
        cs = m.get("callsign", "")
        rest = transcript.strip()
        if rest.lower().startswith(cs.lower()):
            rest = rest[len(cs):].lstrip(" ,:.-")
        return m, (rest or transcript.strip())
    # 4) Persona actif
    for p in enabled:
        if p["id"] == cfg.get("active_persona"):
            return p, transcript.strip()
    return enabled[0], transcript.strip()


def run_copilot():
    import apikeys
    cfg0 = core.get_config()
    apikeys.load_into_env(cfg0.get("llm_provider", "deepseek"), cfg0)
    # 1er démarrage : on attend qu'une clé API soit fournie via l'interface.
    warned = False
    while apikeys.needs_key(core.get_config()):
        if not warned:
            print("En attente d'une clé API — renseigne-la dans l'interface "
                  "(carte « Cerveau (IA) »). L'interface est déjà ouverte.")
            warned = True
        time.sleep(2)
        apikeys.load_into_env(core.get_config().get("llm_provider", "deepseek"),
                              core.get_config())
    if warned:
        print("Clé API détectée. Démarrage du copilote.")

    telemetry = TelemetryListener()
    core.STATE["telemetry"] = telemetry
    monitor = core.STATE["monitor"]      # partagé avec l'interface (rebind live)

    # ------------------------------------------------------------------
    # Commandes de l'avion : carré de touche à l'écran + exécution
    # ------------------------------------------------------------------
    import command_bridge
    import dcs_keys
    import overlay as overlay_mod

    cfg0 = core.get_config()
    ov = None
    if cfg0.get("key_overlay", True):
        try:
            ov = overlay_mod.KeyOverlay(seconds=float(cfg0.get("key_overlay_seconds", 6)))
            print("[carré] affichage de la touche prêt (au-dessus de DCS).")
        except Exception as e:
            print(f"[carré] overlay indisponible : {e}")
            ov = None

    def current_aircraft():
        t = telemetry.get() or {}
        prof = (core.get_config().get("aircraft_profile") or "").strip()
        return prof or t.get("aircraft") or None

    def bridge_now():
        c = core.get_config()
        return command_bridge.CommandBridge(
            core.get_control(), overlay=ov,
            air_bridge=current_aircraft,
            injection=bool(c.get("key_injection", True)),
            display=bool(c.get("display_responses", True)))

    jest = jester.Jester(bridge_now())
    core.STATE["jester"] = jest
    core.STATE["overlay"] = ov
    core.STATE["bridge_factory"] = bridge_now
    if cfg0.get("dcs_install"):
        os.environ["DCS_INSTALL"] = cfg0["dcs_install"]
    if cfg0.get("dcs_saved_games"):
        os.environ["DCS_SAVED_GAMES"] = cfg0["dcs_saved_games"]

    try:
        ac = current_aircraft()
        n = dcs_keys.count(ac)
        print(f"[commandes] {n['total']} commandes connues pour {ac or 'l’avion courant'} "
              f"({n['keyboard']} avec touche clavier).")
    except Exception as e:
        print(f"[commandes] catalogue indisponible : {e}")


    ALL_TOOLS = [
        {
            "name": "get_telemetry",
            "description": (
                "Renvoie l'état de vol instantané du joueur dans DCS : type d'avion, "
                "latitude/longitude, altitude (m), cap (deg), tangage/roulis, vitesse "
                "indiquée et vraie (m/s), Mach, vitesse verticale (m/s), hauteur sol (m)."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "spawn_aircraft",
            "description": (
                "Fait apparaître un groupe d'avions près du joueur (air-start). "
                "Pour escorte/renforts amis (side=friendly) ou ennemis/cibles "
                "(side=enemy). 'aircraft' = identifiant DCS, ex : FA-18C_hornet, "
                "F-16C_50, F-15C, A-10C_2, MiG-29S, Su-27, Su-25, MiG-21Bis, JF-17."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["friendly", "enemy"]},
                    "aircraft": {"type": "string", "description": "identifiant DCS du type"},
                    "mission": {"type": "string", "enum": ["cap", "cas", "tanker", "awacs"], "description": "cap=chasse (engage l'ennemi), cas=appui sol, tanker=ravitailleur (contactable au menu radio), awacs=AWACS. Défaut cap.", "default": "cap"},
                    "count": {"type": "integer", "description": "1 à 4", "default": 1},
                    "relative": {"type": "boolean", "description": "true = bearing_deg RELATIF au nez du joueur (0=devant, 90=3h, 180=derrière, 270=9h) — à utiliser pour 'devant moi', 'à mon X heures', 'sur ma gauche'. false = cap boussole absolu (0=N).", "default": False},
                    "bearing_deg": {"type": "number", "description": "si relative=false : cap boussole (0=N,90=E) ; si relative=true : angle depuis le nez (0=devant)", "default": 0},
                    "distance_nm": {"type": "number", "description": "distance en nm depuis le point de référence", "default": 15},
                    "altitude_ft": {"type": "number", "description": "altitude en pieds", "default": 15000},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "description": "point de référence du placement : player=par rapport au joueur (défaut), mark=repère F10 du joueur, bullseye, airbase/city (fournir 'place'), coords (fournir lat/lon). Le cap+distance s'appliquent depuis ce point.", "default": "player"},
                    "place": {"type": "string", "description": "nom de l'aérodrome ou de la ville (si reference=airbase ou city)"},
                    "lat": {"type": "number", "description": "latitude (si reference=coords)"},
                    "lon": {"type": "number", "description": "longitude (si reference=coords)"},
                },
                "required": ["side", "aircraft"],
            },
        },
        {
            "name": "spawn_ground",
            "description": (
                "Fait apparaître un groupe d'unités AU SOL près du joueur (chars, "
                "DCA/SAM, véhicules, infanterie). side=friendly ou enemy. "
                "'unit_type' = identifiant DCS, ex : 'M-1 Abrams', 'M-2 Bradley', "
                "'Soldier M4', 'Ural-375', 'ZSU-23-4 Shilka', '2S6 Tunguska', "
                "'Strela-10M3', 'T-90', 'BMP-2', 'BTR-80', 'Hummer'. Choisis un type "
                "cohérent (char pour un char, AAA/SAM pour de la DCA)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["friendly", "enemy"]},
                    "unit_type": {"type": "string", "description": "identifiant DCS de l'unité sol"},
                    "count": {"type": "integer", "description": "1 à 6", "default": 1},
                    "relative": {"type": "boolean", "description": "true = bearing_deg RELATIF au nez (0=devant, 90=3h, 180=derrière, 270=9h) pour 'devant moi'/'à mon X heures'. false = cap boussole absolu (0=N).", "default": False},
                    "bearing_deg": {"type": "number", "description": "si relative=false : cap boussole ; si relative=true : angle depuis le nez", "default": 0},
                    "distance_nm": {"type": "number", "description": "distance en nm depuis le point de référence", "default": 2},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "description": "player (défaut), mark (repère F10), bullseye, airbase/city (via 'place'), coords (lat/lon). Mets distance_nm=0 pour spawner PILE sur la référence.", "default": "player"},
                    "place": {"type": "string", "description": "nom d'aérodrome ou de ville (reference=airbase/city)"},
                    "lat": {"type": "number", "description": "latitude (reference=coords)"},
                    "lon": {"type": "number", "description": "longitude (reference=coords)"},
                },
                "required": ["side", "unit_type"],
            },
        },
        {
            "name": "spawn_ship",
            "description": (
                "Fait apparaître des NAVIRES près du joueur (doit être au-dessus de "
                "ou près de l'EAU). unit_type = identifiant DCS, ex : 'CVN_71' "
                "(porte-avions), 'Stennis', 'PERRY' (frégate), 'TICONDEROG', "
                "'MOLNIYA', 'ALBATROS', 'speedboat', 'ELNYA' (ravitailleur). "
                "side=friendly ou enemy."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["friendly", "enemy"]},
                    "unit_type": {"type": "string", "description": "identifiant DCS du navire"},
                    "count": {"type": "integer", "description": "1 à 4", "default": 1},
                    "relative": {"type": "boolean", "default": False},
                    "bearing_deg": {"type": "number", "default": 90},
                    "distance_nm": {"type": "number", "description": "distance en nm depuis le point de référence", "default": 10},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "description": "player (défaut), mark (repère F10), bullseye, airbase/city (via 'place'), coords (lat/lon).", "default": "player"},
                    "place": {"type": "string", "description": "nom d'aérodrome ou de ville (reference=airbase/city)"},
                    "lat": {"type": "number", "description": "latitude (reference=coords)"},
                    "lon": {"type": "number", "description": "longitude (reference=coords)"},
                },
                "required": ["side", "unit_type"],
            },
        },
        {
            "name": "order_engage",
            "description": (
                "Ordonne à TOUTES les unités alliées que tu as fait apparaître "
                "(avions, sol, navires) d'ouvrir le feu / engager l'ennemi."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "spawn_prefab",
            "description": (
                "Fait apparaître un PAQUET tactique préconçu (variante amie/ennemie auto). "
                "name accepte la désignation OTAN/russe ou un nom : sam_long (= S-300 / "
                "SA-10 / Patriot, longue portée), sam_med (= Buk / SA-11 / SA-6 / Hawk), "
                "sam_short (= Tor / SA-15 / SA-8 / Avenger), shorad (DCA courte : Shilka/"
                "Tunguska), armor (colonne blindée/chars), convoy (logistique), infantry "
                "(section), cap (4 chasseurs), strike (2 attaque-sol), carrier (groupe naval). "
                "Ex : « SA-10 », « S-300 », « site SAM longue portée » -> sam_long."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "prefab ou désignation (SA-10, S-300, Buk, colonne blindée, CAP…)"},
                    "side": {"type": "string", "enum": ["friendly", "enemy"]},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "default": "player"},
                    "place": {"type": "string"}, "lat": {"type": "number"}, "lon": {"type": "number"},
                    "relative": {"type": "boolean", "default": False},
                    "bearing_deg": {"type": "number", "default": 90},
                    "distance_nm": {"type": "number", "default": 5},
                },
                "required": ["name", "side"],
            },
        },
        {
            "name": "battlefield_mark",
            "description": (
                "Marque une position : kind=smoke (fumigène), flare (fusée éclairante) "
                "ou circle (cercle sur la carte F10). color=green/red/white/orange/blue. "
                "Positionne via reference (mark/city/coords/player…). Pour 'marque la cible', "
                "demande au pilote un repère F10 (reference=mark)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["smoke", "flare", "circle"], "default": "smoke"},
                    "color": {"type": "string", "enum": ["green", "red", "white", "orange", "blue"], "default": "red"},
                    "radius_nm": {"type": "number", "description": "rayon si kind=circle", "default": 5},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "default": "mark"},
                    "place": {"type": "string"}, "lat": {"type": "number"}, "lon": {"type": "number"},
                    "bearing_deg": {"type": "number", "default": 0},
                    "distance_nm": {"type": "number", "default": 0},
                    "relative": {"type": "boolean", "default": False},
                },
                "required": [],
            },
        },
        {
            "name": "spawn_static",
            "description": (
                "Fait apparaître un objet STATIQUE. kind : fuel (dépôt carburant), "
                "warehouse (entrepôt), hangar, comms (tour), bunker, farp, container, tent. "
                "Positionnement identique aux spawns."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["fuel", "warehouse", "hangar", "comms", "bunker", "farp", "container", "tent"]},
                    "side": {"type": "string", "enum": ["friendly", "enemy"]},
                    "reference": {"type": "string", "enum": ["player", "mark", "bullseye", "airbase", "city", "coords"], "default": "player"},
                    "place": {"type": "string"}, "lat": {"type": "number"}, "lon": {"type": "number"},
                    "relative": {"type": "boolean", "default": False},
                    "bearing_deg": {"type": "number", "default": 90},
                    "distance_nm": {"type": "number", "default": 1},
                },
                "required": ["kind", "side"],
            },
        },
        {
            "name": "highlight_cockpit_control",
            "description": (
                "Encadre visuellement une commande du cockpit pour la montrer au "
                "pilote (comme les missions d'entraînement DCS). Donne le nom en "
                "clair, ex : 'levier de train', 'frein de parking', 'interrupteur "
                "APU', 'batterie'. Idéal pour guider une procédure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"control": {"type": "string",
                                           "description": "nom de la commande à encadrer"}},
                "required": ["control"],
            },
        },
        {
            "name": "clear_cockpit_highlight",
            "description": "Retire l'encadrement de commande du cockpit.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "press_control",
            "description": (
                "EXÉCUTE une commande de l'avion du pilote, comme s'il appuyait dessus : "
                "train d'atterrissage, volets, aérofreins, crosse, perche de "
                "ravitaillement, master arm, feux, pilote automatique, contre-mesures… "
                "Donne le nom en français, tel que le pilote le dirait (ex : « train "
                "d'atterrissage », « sortir le train », « master arm sur armé »). "
                "La touche utilisée s'affiche dans un carré à l'écran. "
                "Réponse ok=false -> dis au pilote ce qui manque (interrupteur cockpit)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"control": {"type": "string",
                                           "description": "commande en français"}},
                "required": ["control"],
            },
        },
        {
            "name": "show_control",
            "description": (
                "Affiche dans un carré à l'écran la TOUCHE d'une commande, sans "
                "l'exécuter : sert à montrer au pilote ce qu'il doit presser pendant "
                "une procédure (démarrage, décollage, atterrissage, combat). "
                "À utiliser systématiquement quand tu cites une touche."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"control": {"type": "string"}},
                "required": ["control"],
            },
        },
        {
            "name": "list_controls",
            "description": (
                "Cherche les commandes de l'avion (libellé exact + touche + zone du "
                "cockpit). À utiliser quand tu ne connais pas le nom exact d'une "
                "commande, ou pour proposer plusieurs variantes au pilote."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"},
                               "limit": {"type": "integer", "default": 6}},
                "required": ["query"],
            },
        },
        {
            "name": "jester",
            "description": (
                "Pilote le menu Jester / Iceman du F-14 pour le pilote. "
                "action=open (ouvre le menu), close (le ferme), item avec value=1..8 "
                "(choisit l'entrée affichée), run avec value='radar' (ouvre et joue un "
                "chemin appris), learn avec value='radar' et keys=[1,3] (mémorise le "
                "chemin). Le menu est contextuel : si l'entrée est inconnue, ouvre-le et "
                "demande le numéro au pilote."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string",
                               "enum": ["open", "close", "item", "run", "learn", "list"]},
                    "value": {"type": "string"},
                    "keys": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["action"],
            },
        },
        {
            "name": "autopilot",
            "description": (
                "Règle l'autopilote : alt_hold (maintien d'altitude), att_hold "
                "(maintien d'assiette), alt_bank (altitude + roulis), level (retour "
                "au vol en palier), alt_hdg (altitude + cap), route (suivi de "
                "route), override, off (débrayage)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string",
                             "enum": ["alt_hold", "att_hold", "alt_bank", "level",
                                      "alt_hdg", "route", "override", "off"]},
                },
                "required": ["mode"],
            },
        },
    ]

    def run_tool(name, tool_input):
        if name == "get_telemetry":
            data = telemetry.get()
            if not data:
                return {"error": "Aucune donnée DCS reçue. En vol ? Export installé ?"}
            if time.time() - data.get("_rx_time", 0) > 3:
                return {"warning": "Données périmées (>3s). Avion en pause ?", **data}
            return data
        if name == "spawn_aircraft":
            ctrl = core.get_control()
            if ctrl is None:
                return {"error": "Canal DCS désactivé. Active le backend dans l'interface."}
            if not hasattr(ctrl, "spawn_aircraft"):
                return {"error": "Le spawn nécessite le backend Hook Lua."}
            a = tool_input or {}
            try:
                ctrl.spawn_aircraft(
                    aircraft=a.get("aircraft", "FA-18C_hornet"),
                    side=a.get("side", "enemy"),
                    count=int(a.get("count", 1)),
                    bearing_deg=float(a.get("bearing_deg", 0)),
                    distance_nm=float(a.get("distance_nm", 15)),
                    altitude_ft=float(a.get("altitude_ft", 15000)),
                    relative=bool(a.get("relative", False)),
                    mission=a.get("mission", "cap"),
                    reference=a.get("reference", "player"),
                    place=a.get("place"), lat=a.get("lat"), lon=a.get("lon"),
                )
                return {"ok": True, "spawned": a}
            except Exception as e:
                return {"error": str(e)}
        if name == "spawn_ship":
            ctrl = core.get_control()
            if ctrl is None or not hasattr(ctrl, "spawn_ship"):
                return {"error": "Nécessite le canal Hook actif."}
            a = tool_input or {}
            try:
                ctrl.spawn_ship(
                    unit_type=a.get("unit_type", "PERRY"),
                    side=a.get("side", "enemy"),
                    count=int(a.get("count", 1)),
                    bearing_deg=float(a.get("bearing_deg", 90)),
                    distance_nm=float(a.get("distance_nm", 10)),
                    relative=bool(a.get("relative", False)),
                    reference=a.get("reference", "player"),
                    place=a.get("place"), lat=a.get("lat"), lon=a.get("lon"),
                )
                return {"ok": True, "spawned": a}
            except Exception as e:
                return {"error": str(e)}
        if name == "order_engage":
            ctrl = core.get_control()
            if ctrl is None or not hasattr(ctrl, "order_engage"):
                return {"error": "Nécessite le canal Hook actif."}
            try:
                ctrl.order_engage()
                return {"ok": True}
            except Exception as e:
                return {"error": str(e)}
        if name in ("spawn_prefab", "battlefield_mark", "spawn_static"):
            ctrl = core.get_control()
            if ctrl is None or not hasattr(ctrl, name):
                return {"error": "Nécessite le canal Hook actif."}
            a = tool_input or {}
            loc = dict(reference=a.get("reference", "player"), place=a.get("place"),
                       lat=a.get("lat"), lon=a.get("lon"),
                       relative=bool(a.get("relative", False)))
            try:
                if name == "spawn_prefab":
                    ctrl.spawn_prefab(a.get("name", ""), side=a.get("side", "enemy"),
                                      bearing_deg=float(a.get("bearing_deg", 90)),
                                      distance_nm=float(a.get("distance_nm", 5)), **loc)
                elif name == "spawn_static":
                    ctrl.spawn_static(a.get("kind", ""), side=a.get("side", "enemy"),
                                      bearing_deg=float(a.get("bearing_deg", 90)),
                                      distance_nm=float(a.get("distance_nm", 1)), **loc)
                else:
                    loc.pop("relative")
                    ctrl.battlefield_mark(a.get("kind", "smoke"), a.get("color", "red"),
                                          radius_nm=float(a.get("radius_nm", 5)),
                                          bearing_deg=float(a.get("bearing_deg", 0)),
                                          distance_nm=float(a.get("distance_nm", 0)),
                                          relative=bool(a.get("relative", False)), **loc)
                return {"ok": True, "action": a}
            except Exception as e:
                return {"error": str(e)}
        if name == "spawn_ground":
            ctrl = core.get_control()
            if ctrl is None or not hasattr(ctrl, "spawn_ground"):
                return {"error": "Nécessite le canal Hook actif."}
            a = tool_input or {}
            try:
                ctrl.spawn_ground(
                    unit_type=a.get("unit_type", "M-1 Abrams"),
                    side=a.get("side", "enemy"),
                    count=int(a.get("count", 1)),
                    bearing_deg=float(a.get("bearing_deg", 0)),
                    distance_nm=float(a.get("distance_nm", 2)),
                    relative=bool(a.get("relative", False)),
                    reference=a.get("reference", "player"),
                    place=a.get("place"), lat=a.get("lat"), lon=a.get("lon"),
                )
                return {"ok": True, "spawned": a}
            except Exception as e:
                return {"error": str(e)}
        if name == "highlight_cockpit_control":
            ctrl = core.get_control()
            if ctrl is None or not hasattr(ctrl, "highlight_control"):
                return {"error": "Nécessite le canal Hook actif."}
            hint = ctrl.highlight_control((tool_input or {}).get("control", ""))
            if hint:
                return {"ok": True, "highlighted": hint}
            return {"error": "Commande introuvable dans ce cockpit."}
        if name == "clear_cockpit_highlight":
            ctrl = core.get_control()
            if ctrl and hasattr(ctrl, "remove_highlight"):
                ctrl.remove_highlight()
            return {"ok": True}
        if name == "jester":
            j = core.STATE.get("jester")
            if j is None:
                return {"error": "Jester indisponible (canal DCS fermé)."}
            a = tool_input or {}
            act = (a.get("action") or "open").lower()
            try:
                if act == "open":
                    return j.open()
                if act == "close":
                    return j.close()
                if act == "item":
                    return j.item(a.get("value") or a.get("n") or 0)
                if act == "run":
                    return j.run_named(a.get("value") or "")
                if act == "learn":
                    return j.learn(a.get("value") or "", a.get("keys") or [])
                return j.known(a.get("value") or None)
            except Exception as e:
                return {"error": str(e)}
        if name in ("press_control", "show_control", "list_controls", "autopilot"):
            br = bridge_now()
            if br is None:
                return {"error": "Commandes avion indisponibles (canal DCS fermé)."}
            a = tool_input or {}
            try:
                if name == "press_control":
                    return br.press(a.get("control", ""))
                if name == "show_control":
                    return br.show(a.get("control", ""))
                if name == "list_controls":
                    return {"commandes": br.list(a.get("query", ""),
                                                 limit=int(a.get("limit", 6)))}
                return br.autopilot(a.get("mode", "alt_hold"))
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"outil inconnu: {name}"}

    histories = {}   # id persona -> historique de conversation (opaque, propre au LLM)
    last_llm_key = None
    persona_monitors = {}   # id -> PTTMonitor (mode per_persona)
    mon_sig = None
    print("\n=== DCS RYZEN Copilote prêt (MULTI-PERSONA, réglages à la volée) ===")
    print("Adresse un persona par indicatif, fréquence ou bouton PTT dédié.")
    print("Commandes avion : dis « sors le train », « master arm », « pilote auto maintien altitude ».")
    print("Sois en vol dans DCS. Ctrl+C pour quitter.\n")

    while True:
        try:
            cfg = core.get_config()   # instantané live à chaque tour

            # (Re)construit les moniteurs PTT par persona si nécessaire.
            if cfg.get("ptt_mode") == "per_persona":
                sig = tuple((p["id"], json.dumps(p.get("ptt"), sort_keys=True))
                            for p in cfg.get("personas", []) if p.get("ptt"))
            else:
                sig = ()
            if sig != mon_sig:
                for m in persona_monitors.values():
                    m.stop()
                persona_monitors = {}
                if cfg.get("ptt_mode") == "per_persona":
                    for p in cfg.get("personas", []):
                        if p.get("ptt"):
                            persona_monitors[p["id"]] = ptt.PTTMonitor(p["ptt"])
                mon_sig = sig

            mic_device = audioio.resolve_input_device(cfg.get("mic_device_name"),
                                                      cfg.get("mic_device"))
            print("\n[Maintiens un push-to-talk pour parler...]")
            ptt_pid, active_mon = _wait_any_ptt(monitor, persona_monitors)
            print("  ... écoute (relâche pour envoyer)")
            audio = _record_active(active_mon, mic_device, cfg.get("mic_device_name"))
            if audio.size < SAMPLE_RATE * 0.3:
                print("  (rien capté : appui trop court ?)")
                core.STATE["status"] = {"heard": "", "error": "appui trop court", "rms": 0.0}
                continue

            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            core.STATE["status"] = {"heard": "", "error": "", "rms": rms}
            if rms < 0.0015:
                print(f"  (micro quasi silencieux : niveau {rms:.5f}) — vérifie le micro "
                      f"choisi (carte Micro) et le mute du casque.")
                core.STATE["status"] = {"heard": "", "rms": rms,
                                        "error": "micro quasi silencieux (niveau %.5f)" % rms}
                continue

            user_text = core.transcribe(audio, cfg["language"])
            core.STATE["status"] = {"heard": user_text or "", "rms": rms,
                                    "error": "" if user_text else "transcription vide"}
            if not user_text:
                print(f"  (rien d'intelligible : niveau {rms:.4f}) — Whisper n'a pas "
                      f"compris ; parle plus près du micro ou essaie le modèle « small ».")
                continue

            control = core.get_control()
            tel = telemetry.get() or {}
            persona, msg = _select_persona(cfg, ptt_pid, user_text, control,
                                           tel.get("aircraft"))
            if persona is None:
                print(f"Toi> {user_text}")
                if cfg.get("freq_required"):
                    print("  (aucun persona sur cette fréquence)")
                continue
            print(f"Toi> [{persona.get('callsign')}] {msg}")

            # ------------------------------------------------------------------
            # Chemin rapide : commande d'avion reconnue SANS IA.
            # Indispensable avec un petit modèle local (4B sur NPU) qui se trompe
            # sur les arguments d'outils : « sors le train » doit marcher à coup
            # sûr et tout de suite, même sans cerveau disponible.
            # ------------------------------------------------------------------
            if cfg.get("voice_fastpath", True):
                try:
                    intent = fastpath.detect(msg, current_aircraft(),
                                             cfg.get("language", "fr"))
                except Exception as e:
                    print(f"[commande directe] analyse impossible : {e}")
                    intent = None
                if intent:
                    br = bridge_now()
                    if intent["action"] == "jester":
                        mode = intent.get("mode")
                        if mode == "open":
                            res = jest.open()
                        elif mode == "close":
                            res = jest.close()
                        elif mode == "item":
                            res = jest.item(intent.get("n") or 0)
                        else:
                            res = jest.run_named(intent.get("name") or "")
                    elif intent["action"] == "volume":
                        cur = float(core.get_config().get("voice_volume", 1.4) or 1.4)
                        new = intent["value"] if intent.get("value") else cur + intent.get("delta", 0)
                        new = max(0.3, min(2.5, round(new, 2)))
                        core.update_config({"voice_volume": new})
                        res = {"ok": True, "label": "volume de la voix", "volume": new}
                    elif intent["action"] == "autopilot":
                        res = br.autopilot(intent["mode"])
                    elif intent["action"] == "show":
                        res = br.show(intent["query"])
                    else:
                        res = br.press(intent["query"])
                    spoken = fastpath.reply(intent, res)
                    print(f"  [commande directe] {intent['action']} "
                          f"{intent.get('mode') or ''} -> ok={res.get('ok')} "
                          f"{res.get('touche') or ''}")
                    if not res.get("ok"):
                        print(f"  [commande directe] {res.get('error')}")
                    core.STATE["status"] = {
                        "heard": user_text, "error": "", "rms": rms,
                        "commande": res.get("label") or "",
                        "touche": res.get("touche") or ""}
                    if res.get("proches"):
                        core.STATE["status"]["proches"] = res["proches"]
                    if spoken:
                        cs = persona.get("callsign", "")
                        print(f"{cs}> {spoken}")
                        core.speak_as(persona.get("voice"), spoken)
                    continue

            # Menu Jester ouvert : « trois » -> entrée 3 (le pilote lit l'écran)
            try:
                if jest.menu_open.get(current_aircraft()):
                    n = fastpath.detect_number(msg)
                    if n:
                        res = jest.item(n)
                        spoken = ("Entrée %d." % n) if res.get("ok") else \
                                 ("Jester : %s" % (res.get("error") or "échec"))
                        print(f"  [jester] entrée {n} -> ok={res.get('ok')}")
                        core.STATE["status"] = {"heard": user_text, "error": "",
                                                "rms": rms, "commande": "Jester %d" % n,
                                                "touche": res.get("touche") or ""}
                        core.speak_as(persona.get("voice"), spoken)
                        continue
            except Exception as e:
                print(f"[jester] {e}")

            # Le cerveau (LLM) est interchangeable. On vide les historiques si on a
            # changé de fournisseur/modèle (formats d'historique incompatibles).
            llm = core.get_llm()
            if core.STATE.get("llm_key") != last_llm_key:
                histories.clear()
                last_llm_key = core.STATE.get("llm_key")

            system_prompt = personas.build_prompt(persona)
            # Avec un petit modèle local, on lui DONNE les libellés exacts :
            # il n'a plus qu'à choisir au lieu d'inventer un nom de commande.
            try:
                cands = fastpath.candidates(msg, current_aircraft(),
                                            cfg.get("language", "fr"), limit=4)
            except Exception:
                cands = []
            if cands:
                system_prompt += ("\n\nCOMMANDES PROCHES DE LA DEMANDE "
                                  "(réutilise le libellé EXACT dans press_control / "
                                  "show_control) : " +
                                  " | ".join("%s (%s)" % (c["label"], c["touche"])
                                             for c in cands))

            # Avec un petit modèle local, on lui DONNE les libellés exacts :
            # il n'a plus qu'à choisir, au lieu d'inventer un nom de commande.
            try:
                cands = fastpath.candidates(msg, current_aircraft(),
                                            cfg.get("language", "fr"), limit=4)
            except Exception:
                cands = []
            if cands:
                system_prompt += ("\n\nCOMMANDES PROCHES DE LA DEMANDE "
                                  "(réutilise le libellé EXACT dans press_control / "
                                  "show_control) : " +
                                  " | ".join("%s (%s)" % (c["label"], c["touche"])
                                             for c in cands))
            tools = personas.role_tools(persona.get("role"), ALL_TOOLS)
            history = histories.get(persona["id"], [])
            try:
                reply, history = llm.converse(system_prompt, tools, history, msg, run_tool)
            except Exception as e:
                print(f"[LLM] {e}")
                continue
            histories[persona["id"]] = history

            spoken = tts.clean_for_speech(reply)
            if spoken:
                cs = persona.get("callsign", "")
                print(f"{cs}> {spoken}")
                if cfg.get("display_responses"):
                    ctrl = core.get_control()
                    if ctrl:
                        try:
                            ctrl.out_text(f"{cs}: {spoken}", 15)
                        except Exception as e:
                            print(f"[affichage DCS échec] {e}")
                if cfg.get("voice_mode") == "srs" and srs.available(cfg):
                    try:
                        srs.transmit(cfg, spoken)
                    except Exception as e:
                        print(f"[SRS échec, repli voix locale] {e}")
                        core.speak_as(persona.get("voice"), spoken)
                else:
                    core.speak_as(persona.get("voice"), spoken)

        except KeyboardInterrupt:
            print("\nArrêt.")
            break
        except Exception as e:
            print(f"[erreur] {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    run_copilot()
