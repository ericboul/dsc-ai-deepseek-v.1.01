"""Pont entre le copilote et les commandes de l'avion.

Trois niveaux, du plus fiable au plus explicatif :
  1. TOUCHE     : la commande est liée au clavier -> on appuie dessus (SendInput).
  2. COMMANDE DCS : pas de touche, mais DCS connaît la commande (LoSetCommand)
                    -> on l'envoie par le canal export (train, PA, volets...).
  3. EXPLICATION : rien de disponible -> on donne le libellé exact, la zone du
                    cockpit et, si elle existe, la touche/le bouton HOTAS lié.

Chaque action affiche la touche dans un carré à l'écran (overlay Windows) et
la rappelle à l'écran de DCS.
"""
import dcs_keys
import win_io

# Commandes SIM de DCS (LoSetCommand) — marchent sur tout appareil qui les
# implémente, même sans raccourci clavier dans le cockpit.
SIM = {
    "gear_up": 430,
    "gear_down": 431,
    "ap_att_hold": 386,        # Autopilot - Attitude Hold
    "ap_alt_bank": 387,        # Autopilot - Altitude And Roll Hold
    "ap_level": 388,           # Autopilot - Transition To Level Flight
    "ap_alt_hold": 389,        # Autopilot - Barometric Altitude Hold
    "ap_alt_hdg": 390,         # Autopilot - Altitude And Heading Hold
    "ap_cancel": 408,          # Autopilot Disengage
    "ap_override_on": 427,
    "ap_override_off": 428,
    "ap_route": 429,           # Route autopilot on/off
    "flaps_on": 145,
    "flaps_off": 146,
    "airbrake_on": 147,
    "airbrake_off": 148,
    "master_arm": 283,         # Switch master arm
    "lights": 175,             # On-board lights
    "jettison_tanks": 178,
    "engine_left_on": 161,
    "engine_left_off": 162,
    "engine_right_on": 163,
    "engine_right_off": 164,
    "weapon_change": 101,
    "cannon": 113,
    "radar_mode": 285,
    "rwr_mode": 286,
}

# modes d'autopilote demandés en français -> commande SIM + libellé
SIM_LABELS = {
    "gear_down": "Train d'atterrissage - SORTIR",
    "gear_up": "Train d'atterrissage - RENTRER",
    "flaps_on": "Volets - SORTIR",
    "flaps_off": "Volets - RENTRER",
    "airbrake_on": "Aérofreins - SORTIR",
    "airbrake_off": "Aérofreins - RENTRER",
    "master_arm": "Master arm",
    "lights": "Feux extérieurs",
    "jettison_tanks": "Largage des réservoirs",
    "ap_alt_hold": "Pilote auto - maintien d'altitude",
    "ap_att_hold": "Pilote auto - maintien d'assiette",
    "ap_alt_bank": "Pilote auto - altitude et roulis",
    "ap_level": "Pilote auto - vol en palier",
    "ap_alt_hdg": "Pilote auto - altitude et cap",
    "ap_cancel": "Pilote auto - débrayage",
    "ap_override_on": "Pilote auto - surcharge",
    "ap_route": "Pilote auto - suivi de route",
}

AP_MODES = {
    "alt_hold": ("ap_alt_hold", "Pilote auto - maintien d'altitude"),
    "altitude": ("ap_alt_hold", "Pilote auto - maintien d'altitude"),
    "maintien altitude": ("ap_alt_hold", "Pilote auto - maintien d'altitude"),
    "alt": ("ap_alt_hold", "Pilote auto - maintien d'altitude"),
    "att_hold": ("ap_att_hold", "Pilote auto - maintien d'assiette"),
    "assiette": ("ap_att_hold", "Pilote auto - maintien d'assiette"),
    "attitude": ("ap_att_hold", "Pilote auto - maintien d'assiette"),
    "alt_bank": ("ap_alt_bank", "Pilote auto - altitude et roulis"),
    "level": ("ap_level", "Pilote auto - retour au vol en palier"),
    "palier": ("ap_level", "Pilote auto - retour au vol en palier"),
    "alt_hdg": ("ap_alt_hdg", "Pilote auto - altitude et cap"),
    "cap": ("ap_alt_hdg", "Pilote auto - altitude et cap"),
    "off": ("ap_cancel", "Pilote auto - débrayage"),
    "cancel": ("ap_cancel", "Pilote auto - débrayage"),
    "debrayage": ("ap_cancel", "Pilote auto - débrayage"),
    "override": ("ap_override_on", "Pilote auto - surcharge (override)"),
    "route": ("ap_route", "Pilote auto - suivi de route"),
}


def sim_for_query(query):
    """Devine la commande SIM correspondant à une demande en français."""
    q = dcs_keys.norm(query)
    if not q:
        return None
    gear = "train" in q or "gear" in q
    if gear:
        if any(w in q for w in ("rentr", "up", "remont", "range")):
            return "gear_up"
        return "gear_down"
    if "volets" in q or "flap" in q:
        return "flaps_off" if any(w in q for w in ("rentr", "up", "0")) else "flaps_on"
    if "aero" in q and ("frein" in q or "brake" in q):
        return "airbrake_off" if any(w in q for w in ("rentr", "off", "coupe")) else "airbrake_on"
    if "armement" in q or "master arm" in q:
        return "master_arm"
    if "feux" in q or "phare" in q or "lumier" in q:
        return "lights"
    if "reservoir" in q and ("largu" in q or "jetti" in q):
        return "jettison_tanks"
    ap_ctx = any(w in (" " + q + " ") for w in (" pilote auto", " autopilote",
                                                " pa ", " maintien", " hold"))
    for k in ("maintien altitude", "alt hold", "altitude", "att hold", "assiette",
              "palier", "niveau", "cap", "debray", "override", "route", "cancel"):
        if k in q and ap_ctx:
            return AP_MODES.get(k, (None,))[0]
    return None


class CommandBridge:
    """Résout, exécute et affiche les commandes de l'appareil du joueur."""

    def __init__(self, control, overlay=None, air_bridge=None, injection=True,
                 display=True):
        self.control = control              # dcs_control.DcsControl ou None
        self.overlay = overlay              # overlay.KeyOverlay ou None
        self.air_bridge = air_bridge        # callable -> type d'avion courant
        self.injection = injection
        self.display = display

    # ---------------------------------------------------------------- utilitaires
    def aircraft(self):
        try:
            return self.air_bridge() if self.air_bridge else None
        except Exception:
            return None

    def _show_box(self, key_text, label, seconds=6, note=""):
        if self.overlay:
            try:
                self.overlay.show(key_text, label, seconds=seconds, note=note)
            except Exception:
                pass
        if self.control and self.display:
            try:
                txt = "%s   ->   %s" % (key_text, label)
                if note:
                    txt += "\n" + note
                self.control.out_text(txt, int(seconds))
            except Exception:
                pass

    @staticmethod
    def combo(row):
        return dcs_keys.combo_label(row)

    # ---------------------------------------------------------------- recherche
    def find(self, query, lang="fr"):
        ac = self.aircraft()
        row = dcs_keys.resolve(query, ac, lang)
        return row

    def list(self, query, lang="fr", limit=6):
        ac = self.aircraft()
        rows = dcs_keys.search(query, ac, lang, limit=limit)
        return [{"label": r.get("label"), "touche": dcs_keys.combo_label(r),
                 "zone": r.get("category") or "",
                 "type": "HOTAS" if (r.get("key") or "").startswith("JOY") else "clavier"}
                for r in rows]

    # ---------------------------------------------------------------- affichage
    def show(self, query, lang="fr", seconds=8):
        row = self.find(query, lang)
        ac = self.aircraft()
        if not row:
            alt = dcs_keys.search(query, ac, lang, limit=3)
            self._show_box("?", query, seconds,
                           "Commande non trouvée" if not alt else "")
            return {"ok": False, "error": "commande introuvable",
                    "proches": [a.get("label") for a in alt]}
        combo = self.combo(row)
        note = row.get("category") or ""
        if not combo:
            note = (note + " · " if note else "") + "pas de touche : interrupteur cockpit"
        self._show_box(combo or "COCKPIT", row.get("label", ""), seconds, note)
        return {"ok": True, "label": row.get("label"), "touche": combo,
                "zone": row.get("category") or "",
                "affichage": "carré à l'écran"}

    # ---------------------------------------------------------------- exécution
    def press(self, query, lang="fr", seconds=6):
        ac = self.aircraft()
        row = dcs_keys.resolve(query, ac, lang)
        # 1) touche clavier liée
        if row and row.get("key") and not str(row["key"]).startswith("JOY"):
            if not self.injection:
                self._show_box(self.combo(row), row.get("label", ""), seconds,
                               "injection clavier désactivée")
                return {"ok": False, "label": row.get("label"),
                        "touche": self.combo(row),
                        "error": "injection clavier désactivée dans la config"}
            res = win_io.press_keys(row.get("mods") or [], row["key"])
            self._show_box(self.combo(row), row.get("label", ""), seconds)
            if res.get("ok"):
                return {"ok": True, "label": row.get("label"),
                        "touche": self.combo(row), "via": "touche clavier"}
            return {"ok": False, "label": row.get("label"),
                    "touche": self.combo(row), "error": res.get("error")}
        # 2) commande SIM (même sans touche liée)
        cmd = sim_for_query(query) or (sim_for_query(row.get("label") if row else "") if row else None)
        if cmd:
            if self.control and hasattr(self.control, "sim_command"):
                r = self.control.sim_command(SIM[cmd])
                # libellé de la commande SIM (plus juste que la ligne trouvée)
                label = SIM_LABELS.get(cmd) or (row or {}).get("label") or cmd
                combo = self.combo(row) if row else ""
                self._show_box(combo or "DCS", label, seconds,
                               "commande DCS envoyée")
                if r and str(r).startswith("ERR"):
                    return {"ok": False, "label": label, "error": str(r)}
                return {"ok": True, "label": label, "touche": combo,
                        "via": "commande DCS (sans touche)"}
        # 3) rien d'exécutable : on explique
        if row:
            combo = self.combo(row)
            hotas = combo if str(row.get("key") or "").startswith("JOY") else ""
            note = row.get("category") or ""
            self._show_box(combo or "COCKPIT", row.get("label", ""), seconds,
                           ("sur ton HOTAS" if hotas else "interrupteur cockpit"))
            return {"ok": False, "label": row.get("label"), "touche": combo,
                    "zone": row.get("category") or "",
                    "hotas": hotas,
                    "error": ("commande sans raccourci clavier : interrupteur à "
                              "cliquer en cockpit"
                              + (" (ou %s)" % hotas if hotas else "")
                              + " — pour que je puisse l'actionner, lie-la dans "
                                "Options > Commandes de DCS")}
        alt = dcs_keys.search(query, ac, lang, limit=4)
        self._show_box("?", query, seconds, "introuvable")
        return {"ok": False, "error": "commande introuvable",
                "proches": [a.get("label") for a in alt]}

    # ---------------------------------------------------------------- autopilote
    def autopilot(self, mode="alt_hold", lang="fr"):
        key = dcs_keys.norm(mode)
        hit = AP_MODES.get(key)
        if not hit:
            for k, v in AP_MODES.items():
                if k in key or key in k:
                    hit = v
                    break
        if not hit:
            return {"ok": False, "error": "mode d'autopilote inconnu",
                    "modes": sorted({v[1] for v in AP_MODES.values()})}
        cmd, label = hit
        # 1) touche liée à ce mode dans l'appareil (plus fidèle au cockpit).
        #    On refuse explicitement la palette NWS/AP et la coupure : appuyer
        #    dessus DÉBRAYERAIT l'autopilote au lieu de l'engager.
        ac = self.aircraft()
        mode_words = ("maintien", "altitude", "assiette", "palier", "niveau", "cap")
        row = None
        for cand in dcs_keys.search("pilote auto " + label.split("-")[-1], ac, lang, limit=6):
            lab = dcs_keys.norm(cand.get("label", ""))
            if not cand.get("key") or str(cand["key"]).startswith("JOY"):
                continue
            if any(w in lab for w in ("coupure", "palette", "debray", "disengage", "nws")):
                continue
            if any(w in lab for w in mode_words):
                row = cand
                break
        if row and row.get("key") and not str(row["key"]).startswith("JOY"):
            res = win_io.press_keys(row.get("mods") or [], row["key"])
            self._show_box(self.combo(row), row.get("label", ""), 6, "autopilote")
            if res.get("ok"):
                return {"ok": True, "label": row.get("label"),
                        "touche": self.combo(row), "via": "touche clavier"}
        # 2) commande SIM
        if self.control and hasattr(self.control, "sim_command"):
            r = self.control.sim_command(SIM[cmd])
            self._show_box("PA", label, 6, "envoyé à DCS")
            if r and str(r).startswith("ERR"):
                return {"ok": False, "label": label, "error": str(r)}
            return {"ok": True, "label": label, "via": "commande DCS"}
        return {"ok": False, "label": label, "error": "canal DCS indisponible"}
