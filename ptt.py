"""Push-to-talk : abstraction clavier + joystick/HOTAS (DirectInput via pygame).

- capture_binding() : attend qu'on presse UNE touche clavier OU UN bouton
  joystick/HOTAS, et renvoie le binding correspondant.
- PTTMonitor : surveille en continu un binding et expose .pressed (bool).
"""
import threading
import time

import keyboard

# pygame est importé paresseusement pour ne pas ouvrir de sous-système inutile.
_pygame = None


def _pg():
    global _pygame
    if _pygame is None:
        import pygame
        pygame.init()
        pygame.joystick.init()
        _pygame = pygame
    return _pygame


def list_joysticks():
    pg = _pg()
    pg.joystick.quit()
    pg.joystick.init()
    out = []
    for i in range(pg.joystick.get_count()):
        j = pg.joystick.Joystick(i)
        j.init()
        out.append({"index": i, "name": j.get_name(),
                    "guid": j.get_guid(), "buttons": j.get_numbuttons()})
    return out


def _pretty_key(name):
    special = {"right ctrl": "Ctrl droit", "left ctrl": "Ctrl gauche",
               "right shift": "Maj droite", "left shift": "Maj gauche",
               "right alt": "Alt droit", "left alt": "Alt gauche",
               "space": "Espace"}
    return special.get(name, (name or "?").upper())


def capture_binding(timeout=15.0):
    """Bloque jusqu'à un appui clavier OU bouton joystick. Renvoie un dict binding
    ou None si timeout."""
    result = {}

    def on_key(e):
        if e.event_type == "down" and not result and e.name:
            result["b"] = {"type": "keyboard", "key": e.name,
                           "label": _pretty_key(e.name)}

    hook = keyboard.hook(on_key)

    pg = _pg()
    pg.joystick.quit()
    pg.joystick.init()
    joys = []
    for i in range(pg.joystick.get_count()):
        j = pg.joystick.Joystick(i)
        j.init()
        joys.append(j)

    # État de référence : on relève l'état actuel de TOUS les boutons avant de
    # commencer. Ainsi un interrupteur/switch déjà maintenu (fréquent sur les
    # bases WINWING/VKB/Virpil) ne sera PAS pris pour un nouvel appui.
    pg.event.pump()
    time.sleep(0.05)
    pg.event.pump()
    prev = {}
    for jidx, j in enumerate(joys):
        for b in range(j.get_numbuttons()):
            prev[(jidx, b)] = bool(j.get_button(b))

    start = time.time()
    try:
        while not result and (time.time() - start) < timeout:
            pg.event.pump()
            for jidx, j in enumerate(joys):
                for b in range(j.get_numbuttons()):
                    val = bool(j.get_button(b))
                    # On ne réagit qu'à une VRAIE transition relâché -> pressé
                    # survenue PENDANT la capture.
                    if val and not prev[(jidx, b)]:
                        result["b"] = {
                            "type": "joystick", "joy_index": jidx,
                            "joy_name": j.get_name(), "guid": j.get_guid(),
                            "button": b,
                            "label": f"{j.get_name()} — Bouton {b + 1}",
                        }
                    prev[(jidx, b)] = val
            time.sleep(0.02)
    finally:
        keyboard.unhook(hook)
    return result.get("b")


# Certaines dispositions Windows renomment les touches (« ctrl droite » au lieu
# de « right ctrl ») : on accepte les variantes pour que le PTT par défaut
# fonctionne aussi sur un clavier français.
KEY_ALIASES = {
    "right ctrl": {"right ctrl", "ctrl droite", "ctrl derecha", "rechte strg",
                   "ctrl destro", "ctrl direita"},
    "left ctrl": {"left ctrl", "ctrl gauche", "ctrl izquierda", "linke strg",
                  "ctrl sinistro", "ctrl esquerda"},
    "right shift": {"right shift", "maj droite", "shift derecha", "rechte umschalt"},
    "left shift": {"left shift", "maj gauche", "shift izquierda", "linke umschalt"},
    "right alt": {"right alt", "alt droite", "alt gr"},
    "left alt": {"left alt", "alt gauche"},
    "space": {"space", "espace", "espacio", "leertaste"},
    "enter": {"enter", "entrée", "entree", "intro", "return", "eingabe"},
    "escape": {"escape", "esc", "echap", "échappe"},
}


def _key_variants(key):
    key = (key or "").lower().strip()
    return KEY_ALIASES.get(key, {key})


class PTTMonitor:
    """Surveille un binding et met à jour .pressed en continu.

    Le clavier est suivi par un hook (et non plus seulement par
    keyboard.is_pressed) : selon la disposition Windows, une touche peut
    s'appeler « ctrl droite » au lieu de « right ctrl », avec un code scan
    différent — is_pressed ne la voyait alors jamais.
    """

    def __init__(self, binding):
        self.binding = binding
        self.pressed = False
        self._stop = False
        self._paused = False
        self._names = set()
        self._scans = set()
        self._lock = threading.Lock()
        self._hook = keyboard.hook(self._on_event, suppress=False)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _on_event(self, event):
        with self._lock:
            name = (event.name or "").lower()
            if event.event_type == "down":
                self._names.add(name)
                self._scans.add(event.scan_code)
            else:
                self._names.discard(name)
                self._scans.discard(event.scan_code)

    def rebind(self, binding):
        self.binding = binding
        with self._lock:
            self._names.clear()
            self._scans.clear()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._stop = True
        try:
            keyboard.unhook(self._hook)
        except Exception:
            pass

    def _find_joy(self, binding):
        pg = _pg()
        pg.joystick.quit()
        pg.joystick.init()
        # priorité au GUID, sinon à l'index, sinon au nom
        for i in range(pg.joystick.get_count()):
            j = pg.joystick.Joystick(i)
            j.init()
            if binding.get("guid") and j.get_guid() == binding["guid"]:
                return j
        for i in range(pg.joystick.get_count()):
            j = pg.joystick.Joystick(i)
            j.init()
            if i == binding.get("joy_index"):
                return j
        return None

    def _loop(self):
        joy = None
        cur_guid = None
        while not self._stop:
            if self._paused:
                self.pressed = False
                time.sleep(0.02)
                continue
            b = self.binding
            try:
                if not b:
                    self.pressed = False
                elif b["type"] == "keyboard":
                    key = (b.get("key") or "").lower()
                    with self._lock:
                        names = set(self._names)
                        scans = set(self._scans)
                    variants = _key_variants(key)
                    hit = bool(names & variants)
                    if not hit and scans:
                        for variant in variants:
                            try:
                                wanted = set(keyboard.key_to_scan_codes(variant))
                            except Exception:
                                wanted = set()
                            if wanted & scans:
                                hit = True
                                break
                    if not hit:
                        try:
                            hit = bool(key) and keyboard.is_pressed(key)
                        except Exception:
                            hit = False
                    self.pressed = hit
                else:
                    pg = _pg()
                    if joy is None or cur_guid != b.get("guid"):
                        joy = self._find_joy(b)
                        cur_guid = b.get("guid")
                    pg.event.pump()
                    self.pressed = bool(joy.get_button(b["button"])) if joy else False
            except Exception:
                self.pressed = False
            time.sleep(0.01)
