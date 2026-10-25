"""Menu Jester / Iceman du F-14 : le copilote le pilote pour toi.

Dans le F-14 (Heatblur), le menu Jester s'ouvre au clavier : « Toggle Menu »
(touche A par défaut), les entrées se choisissent avec Ctrl+1 … Ctrl+8, et
« Close Menu » (Maj+A) le referme. Le module F-14BU hérite du profil F-14 :
ces touches existent donc aussi en F-14BU.

Le menu est CONTEXTUEL : les numéros changent selon l'écran. Deux modes :
  - numéros appris      : « jester apprends radar = 1 3 » -> mémorisé par avion ;
  - à la voix           : le menu est ouvert, le pilote lit les numéros,
                          « trois » -> Ctrl+3.
"""
import json
import os
import time

import dcs_keys

HERE = os.path.dirname(os.path.abspath(__file__))
MENU_FILE = os.path.join(HERE, "jester_menu.json")
KEY_DELAY = 0.45          # temps laissé au menu pour s'afficher / se rafraîchir


def _load():
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    try:
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class Jester:
    """Pilote le menu Jester : ouvrir, choisir, fermer, séquences, apprentissage."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.menu_open = {}        # aircraft -> bool (notre propre suivi)

    # ------------------------------------------------------------------ outils
    def _aircraft(self):
        try:
            return self.bridge.aircraft()
        except Exception:
            return None

    def available(self):
        """True si l'appareil a bien un menu Jester (F-14)."""
        row = dcs_keys.resolve("toggle menu jester", self._aircraft(), "fr")
        if not row:
            return False
        cat = dcs_keys.norm(row.get("category", ""))
        return "jester" in cat or "iceman" in cat or "menu" in dcs_keys.norm(row.get("label", ""))

    # ------------------------------------------------------------------ touches
    def _press_query(self, query, label_if_missing=None):
        ac = self._aircraft()
        row = dcs_keys.resolve(query, ac, "fr")
        if not row or not row.get("key") or str(row["key"]).startswith("JOY"):
            return {"ok": False, "label": label_if_missing or query,
                    "error": "touche du menu Jester introuvable dans ce profil"}
        from win_io import press_keys
        res = press_keys(row.get("mods") or [], row["key"])
        try:
            self.bridge._show_box(dcs_keys.combo_label(row), row.get("label", ""),
                                  3, "menu Jester")
        except Exception:
            pass
        if res.get("ok"):
            return {"ok": True, "label": row.get("label"), "touche": dcs_keys.combo_label(row)}
        return {"ok": False, "label": row.get("label"),
                "touche": dcs_keys.combo_label(row), "error": res.get("error")}

    # ------------------------------------------------------------------ actions
    def open(self):
        ac = self._aircraft()
        res = self._press_query("toggle menu", "Toggle Menu")
        if res.get("ok"):
            self.menu_open[ac] = True
        return res

    def close(self):
        ac = self._aircraft()
        res = self._press_query("close menu", "Close Menu")
        if res.get("ok"):
            self.menu_open[ac] = False
        return res

    def item(self, n):
        """Choisit l'entrée n (1 à 8) du menu affiché."""
        try:
            n = int(n)
        except Exception:
            return {"ok": False, "error": "numéro d'entrée invalide"}
        if not 1 <= n <= 8:
            return {"ok": False, "error": "le menu Jester va de 1 à 8"}
        res = self._press_query("command %d" % n, "Command %d" % n)
        if res.get("ok"):
            self.menu_open[self._aircraft()] = True
        return res

    def path(self, nums, close_after=True):
        """Séquence d'entrées (menu déjà ouvert) : [1, 3] -> Ctrl+1 puis Ctrl+3."""
        done = []
        for i, n in enumerate(nums):
            if i:
                time.sleep(KEY_DELAY)
            res = self.item(n)
            if not res.get("ok"):
                return {"ok": False, "error": res.get("error"), "done": done}
            done.append(n)
        if close_after:
            time.sleep(KEY_DELAY)
            self.close()
        return {"ok": True, "path": done, "label": "Jester " + " > ".join(map(str, done))}

    # ------------------------------------------------------------------ mémoire
    def learn(self, name, nums):
        """Retient « radar = 1 3 » pour cet appareil."""
        ac = self._aircraft() or "default"
        data = _load()
        data.setdefault(ac, {})[dcs_keys.norm(name)] = [int(x) for x in nums]
        _save(data)
        return {"ok": True, "avion": ac, "commande": dcs_keys.norm(name), "chemin": nums}

    def known(self, name=None):
        ac = self._aircraft() or "default"
        data = _load().get(ac, {})
        if name is None:
            return {"ok": True, "avion": ac, "commandes": data}
        return data.get(dcs_keys.norm(name))

    def run_named(self, name):
        """« va sur radar » : ouvre le menu, joue le chemin appris, referme.

        Si le chemin n'est pas connu, ouvre le menu et demande le numéro.
        """
        key = dcs_keys.norm(name)
        nums = None
        data = _load().get(self._aircraft() or "default", {})
        if key in data:
            nums = data[key]
        else:
            # correspondance souple (« radar air air » -> « radar »)
            for k, v in data.items():
                if k and (k in key or key in k):
                    nums = v
                    break
        opened = self.open()
        if not opened.get("ok"):
            return opened
        if not nums:
            return {"ok": True, "menu": "ouvert", "demande_numero": True,
                    "message": "menu Jester ouvert : dis le numéro de l'entrée"}
        time.sleep(KEY_DELAY)
        return self.path(nums, close_after=True)
