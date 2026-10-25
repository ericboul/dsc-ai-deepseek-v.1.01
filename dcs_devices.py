"""Identifiants numériques des devices et commandes d'un module DCS.

Les profils d'entrée désignent les interrupteurs par des symboles
(`devices.AFCS`, `device_commands.AP_Engage`). Pour les actionner depuis
l'extérieur, il faut leurs NUMÉROS, que DCS calcule dans `devices.lua` et
`command_defs.lua` avec des compteurs successifs.

Ce module rejoue ces compteurs (mini-interprète Lua, sans dépendance) et
renvoie les numéros. Validation croisée possible avec les fichiers
`.diff.lua` du joueur, où DCS écrit lui-même les numéros (`d3002…cd13…`).
"""
import os
import re

import dcs_keys

_SYM = re.compile(r"^[\w.]+$")


class _Counters:
    """Rejoue `local count = X` + `counter()` + `count = start_command + N`."""

    def __init__(self):
        self.vars = {}
        self.funcs = {}      # counter -> variable qu'il incrémente
        self.tables = {}     # "table.SYM" -> numéro
        self.devices = {}    # "NAME" -> numéro

    # ------------------------------------------------------------------ Lua léger
    def feed(self, text):
        lines = text.splitlines()
        var_re = re.compile(r"^\s*(?:local\s+)?(\w+)\s*=\s*([\w.]+)\s*(?:\+\s*(\d+))?\s*$")
        fn_re = re.compile(r"^\s*(?:local\s+)?function\s+(\w+)\s*\(")
        inc_re = re.compile(r"(\w+)\s*=\s*\1\s*\+\s*1")
        table_re = re.compile(r"^\s*(\w+)\s*=\s*\{\s*$")
        table_next = re.compile(r"^\s*(\w+)\s*=\s*$")
        dev_re = re.compile(r"^\s*devices\[\s*[\"'](\w+)[\"']\s*\]\s*=\s*(.+?)\s*,?\s*$")
        entry_re = re.compile(r"^\s*(\w+)\s*=\s*([^,{}\n]+?)\s*,?\s*$")

        cur_fn = None
        table = None
        pending = None      # « nom = » puis « { » à la ligne suivante
        depth = 0
        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            m = fn_re.match(line)
            if m:
                cur_fn = m.group(1)
                self.funcs.setdefault(cur_fn, None)
                continue
            if cur_fn and self.funcs.get(cur_fn) is None:
                mi = inc_re.search(line)
                if mi:
                    self.funcs[cur_fn] = mi.group(1)
                    cur_fn = None
                    continue

            # device
            md = dev_re.match(line)
            if md:
                self.devices[md.group(1)] = self._eval(md.group(2))
                continue

            # ouverture de table (sur la même ligne, ou « nom = » puis « { »)
            if pending and line.startswith("{"):
                table, depth, pending = pending, 1, None
                continue
            mt = table_re.match(line)
            if mt and depth == 0:
                table = mt.group(1)
                depth = 1
                continue
            mtn = table_next.match(line)
            if mtn and depth == 0:
                pending = mtn.group(1)
                continue
            if table is not None:
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    table = None
                    depth = 0
                    continue
                me = entry_re.match(line)
                if me and "=" in line and not line.startswith(("--", "return")):
                    val = self._eval(me.group(2))
                    if val is not None:
                        self.tables["%s.%s" % (table, me.group(1))] = val
                continue

            mv = var_re.match(line)
            if mv and mv.group(2) != mv.group(1):
                base = mv.group(2)
                val = self.vars.get(base)
                if val is None:
                    try:
                        val = int(base)
                    except ValueError:
                        continue
                if mv.group(3):
                    val += int(mv.group(3))
                self.vars[mv.group(1)] = val
        return self

    def _eval(self, expr):
        e = (expr or "").strip().rstrip(",;").strip()
        if not e:
            return None
        if e in self.devices:                     # devices.XXX / NAME
            return self.devices.get(e)
        key = e.split(".")[-1]
        if e.startswith("devices.") or key in self.devices:
            return self.devices.get(key)
        if e in self.tables:
            return self.tables[e]
        if key in self.tables:
            return self.tables[key]
        m = re.fullmatch(r"(\w+)\s*\+\s*(\d+)", e)
        if m:
            base = self.vars.get(m.group(1), 0)
            return base + int(m.group(2))
        if re.fullmatch(r"\d+", e):
            return int(e)
        m = re.fullmatch(r"(\w+)\s*\(\s*\)", e)
        if m and m.group(1) in self.funcs:
            var = self.funcs[m.group(1)]
            if var:
                self.vars[var] = self.vars.get(var, 0) + 1
                return self.vars[var]
        if e in self.vars:
            return self.vars[e]
        return None


class ModuleIds:
    """Numéros de devices/commandes d'un module (F-14, FA-18C, F-15E…)."""

    def __init__(self, module_dir):
        self.dir = module_dir
        self.devices = {}
        self.commands = {}
        self._load()

    def _candidates(self):
        d = self.dir
        out = []
        for sub in ("Cockpit/Scripts", "Cockpit"):
            for name in ("devices.lua", "command_defs.lua"):
                p = os.path.join(d, *sub.split("/"), name)
                if os.path.isfile(p):
                    out.append((name, p))
        if not out:                       # modules imbriqués (F14BU -> F14)
            root = dcs_keys.dcs_install()
            if root:
                for base in ("Mods/aircraft", "CoreMods/aircraft"):
                    out.extend(("%s" % n, p) for n, p in [])
        return out

    def _inherited(self):
        """Fichiers devices/command_defs hérités (F-14BU -> F14/Cockpit)."""
        root = dcs_keys.dcs_install()
        out = []
        inp = os.path.join(self.dir, "Input")
        if not (root and os.path.isdir(inp)):
            return out
        for prof in os.listdir(inp):
            pdir = os.path.join(inp, prof, "keyboard")
            if not os.path.isdir(pdir):
                continue
            for f in os.listdir(pdir):
                if not f.endswith(".lua"):
                    continue
                try:
                    txt = dcs_keys._strip_lua_comments(
                        open(os.path.join(pdir, f), encoding="utf-8", errors="ignore").read())
                except Exception:
                    continue
                bases = dict(re.findall(r'local\s+(\w+)\s*=\s*folder\s*\.\.\s*"([^"]+)"', txt))
                for var, rel in re.findall(r'dofile\(\s*(\w+)\s*\.\.\s*"([^"]+)"\s*\)', txt):
                    if var not in bases:
                        continue
                    path = os.path.normpath(os.path.join(pdir, bases[var], rel))
                    if os.path.isfile(path) and path not in out:
                        out.append(path)
        return out

    def _load(self):
        try:
            self._load_from(self._candidates())
        except Exception:
            pass
        if not self.devices or not self.commands:
            try:
                files = self._inherited()
                self._load_from([(os.path.basename(p), p) for p in files])
            except Exception:
                pass

    def _load_from(self, pairs):
        for name, path in pairs:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    txt = dcs_keys._strip_lua_comments(f.read())
            except Exception:
                continue
            c = _Counters().feed(txt)
            if name.endswith("devices.lua"):
                self.devices.update(c.devices)
            elif name.endswith("command_defs.lua"):
                self.commands.update(c.tables)

    # ------------------------------------------------------------------ accès
    def device_id(self, symbol):
        """'devices.AFCS' / 'AFCS' -> numéro."""
        if symbol is None:
            return None
        s = str(symbol).split(".")[-1]
        if isinstance(symbol, int):
            return symbol
        try:
            return int(s)
        except ValueError:
            pass
        return self.devices.get(s)

    def command_id(self, symbol):
        """'device_commands.AP_Engage' / 'AP_Engage' / 3005 -> numéro."""
        if symbol is None:
            return None
        s = str(symbol)
        if s.isdigit():
            return int(s)
        if "." in s:
            tail = s.split(".")[-1]
            return self.commands.get(s) or self.commands.get(tail) or self.commands.get(s.split(".")[0] + "." + tail)
        return self.commands.get(s)

    def resolve_row(self, row):
        """(device_id, command_id, value) pour une ligne du catalogue."""
        row = row or {}
        dev = self.device_id(row.get("device"))
        cmd = self.command_id(row.get("command"))
        if dev is None or cmd is None:
            return None
        val = row.get("value")
        if val is None:
            val = 1.0
        return dev, cmd, float(val)


_CACHE = {}


def for_aircraft(aircraft_type, root=None):
    """ModuleIds de l'appareil, ou None."""
    key = aircraft_type
    if key in _CACHE:
        return _CACHE[key]
    found = dcs_keys.find_aircraft(aircraft_type, root)
    obj = None
    if found:
        obj = ModuleIds(found[0])
    _CACHE[key] = obj
    return obj
