"""Sélection et ouverture des micros.

PortAudio énumère chaque micro une fois par API (MME, DirectSound, WASAPI,
WDM-KS). On expose TOUS les micros (avec leur API) en préférant WASAPI pour
l'ouverture, et on peut ré-énumérer à chaud : un casque Bluetooth branché après
le démarrage de l'application n'apparaît qu'après ré-initialisation de PortAudio.
"""
import sounddevice as sd

_API_ORDER = ("wasapi", "mme", "directsound", "wdm-ks")


def refresh_devices():
    """Ré-énumère les périphériques (indispensable après un branchement)."""
    try:
        sd._terminate()
        sd._initialize()
        return True
    except Exception:
        return False


def _api_rank(name):
    low = (name or "").lower()
    for i, key in enumerate(_API_ORDER):
        if key in low:
            return i
    return len(_API_ORDER)


# entrées « techniques » que Windows n'affiche pas comme des micros
_SKIP = ("mappeur de sons", "sound mapper", "pilote de capture audio principal",
         "primary sound capture", "haut-parleur", "speakers", "sortie",
         "stereo input", "mixage stéréo")


def _is_junk(name):
    low = (name or "").lower()
    return any(k in low for k in _SKIP)


def _clean(name):
    """Nom lisible : coupe les suffixes techniques des pilotes."""
    n = (name or "").strip()
    for marker in (" (@System32", "(@System32"):
        if marker in n:
            n = n.split(marker)[0]
    return n.strip()


def list_input_devices(refresh=False):
    """Micros disponibles, toutes API confondues, dédupliqués par nom.

    Chaque entrée : {"index", "name", "hostapi", "channels", "is_default"}.
    L'index renvoyé est celui à passer à sounddevice (donc ouvrable tel quel).
    """
    has = sd.query_hostapis()
    devs = sd.query_devices()
    entries = []
    for i, d in enumerate(devs):
        if d["max_input_channels"] <= 0:
            continue
        name = _clean(d["name"])
        if "loopback" in name.lower() or _is_junk(name):
            continue
        if "WDM-KS" in has[d["hostapi"]]["name"]:
            continue          # mode exclusif : échoue à l'ouverture, source de doublons
        entries.append({
            "index": i,
            "name": name,
            "hostapi": has[d["hostapi"]]["name"],
            "channels": d["max_input_channels"],
            "is_default": (i == sd.default.device[0]),
        })

    if refresh or len({e["name"] for e in entries}) < 2:
        if refresh_devices():
            has = sd.query_hostapis()
            devs = sd.query_devices()
            entries = []
            for i, d in enumerate(devs):
                nm = _clean(d["name"])
                if d["max_input_channels"] <= 0 or "loopback" in nm.lower() or _is_junk(nm):
                    continue
                if "WDM-KS" in has[d["hostapi"]]["name"]:
                    continue
                entries.append({
                    "index": i,
                    "name": nm,
                    "hostapi": has[d["hostapi"]]["name"],
                    "channels": d["max_input_channels"],
                    "is_default": (i == sd.default.device[0]),
                })

    # dédoublonnage par nom : on garde l'API la mieux classée (WASAPI d'abord)
    best = {}
    for e in entries:
        # clé = 24 premiers caractères (MME tronque) + canaux : deux variantes
        # réelles du même nom (« … (Communications) ») ne sont pas fusionnées.
        key = (e["name"].strip().lower()[:24], e["channels"])
        cur = best.get(key)
        if cur is None or _api_rank(e["hostapi"]) < _api_rank(cur["hostapi"]):
            best[key] = e

    out = list(best.values())
    out.sort(key=lambda e: (_api_rank(e["hostapi"]), not e["is_default"], e["name"].lower()))
    return out


def _match(name, devs):
    if not name:
        return None
    for d in devs:
        if d["name"] == name:
            return d["index"]
    low = name.strip().lower()
    for d in devs:
        n = d["name"].strip().lower()
        if low in n or n in low:
            return d["index"]
    return None


def _openable(index):
    """L'index existe-t-il vraiment et accepte-t-il l'enregistrement ?"""
    try:
        d = sd.query_devices(index)
        if d["max_input_channels"] <= 0:
            return False
        if "WDM-KS" in sd.query_hostapis()[d["hostapi"]]["name"]:
            return False        # mode exclusif : échoue à l'ouverture
        return True
    except Exception:
        return False


def resolve_input_device(name, fallback_index=None):
    """Index du micro choisi. On retrouve par NOM (les index changent quand on
    branche un casque), et on ne fait confiance à l'index mémorisé que s'il
    pointe encore sur un micro ouvrable : sinon -> micro par défaut."""
    idx = _match(name, list_input_devices())
    if idx is not None:
        return idx
    # le matériel a peut-être changé depuis le démarrage : on ré-énumère
    idx = _match(name, list_input_devices(refresh=True))
    if idx is not None:
        return idx
    if fallback_index is not None and _openable(fallback_index):
        return fallback_index
    return None


def resolve_output_device(name):
    """Retrouve l'index d'un périphérique de SORTIE par son nom (WASAPI en priorité).
    Match exact puis sous-chaîne. None = défaut."""
    if not name:
        return None
    devs = sd.query_devices()
    has = sd.query_hostapis()
    cands = [(i, d) for i, d in enumerate(devs) if d["max_output_channels"] > 0]
    cands.sort(key=lambda x: _api_rank(has[x[1]["hostapi"]]["name"]))
    for i, d in cands:
        if d["name"] == name:
            return i
    low = name.lower()
    for i, d in cands:
        n = d["name"].lower()
        if low in n or n in low:
            return i
    return None


def _candidates(name, index):
    """Indices à essayer pour un micro : celui choisi, puis les mêmes endpoints
    via une autre API (WASAPI Bluetooth qui refuse la synchro -> MME), puis défaut."""
    out = []
    if index is not None:
        out.append(index)
    if name:
        low = name.strip().lower()
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] <= 0:
                continue
            api = sd.query_hostapis()[d["hostapi"]]["name"]
            if "WDM-KS" in api:
                continue
            n = _clean(d["name"]).strip().lower()
            if n == low or n[:24] == low[:24]:
                if i not in out:
                    out.append(i)
    out.append(None)          # micro par défaut du système
    return out


def open_input_stream(device=None, samplerate=16000, channels=1, name=None):
    """Ouvre un flux d'entrée en essayant plusieurs API.

    Renvoie (stream, index_utilisé). Lève la dernière erreur si tout échoue.
    Indispensable pour les casques Bluetooth : leur endpoint WASAPI refuse
    parfois la synchro (WdmSyncIoctl) alors que l'entrée MME fonctionne.
    """
    last = None
    for idx in _candidates(name, device):
        st = None
        try:
            st = sd.InputStream(samplerate=samplerate, channels=channels, dtype="float32",
                                device=idx, extra_settings=input_extra_settings(idx))
            st.start()
            return st, idx
        except Exception as e:
            last = e
            if st is not None:
                try:
                    st.close()
                except Exception:
                    pass
    raise RuntimeError("aucun micro utilisable : %s" % last)


def input_extra_settings(device):
    """WasapiSettings(auto_convert) si le device est WASAPI, sinon None.
    Valable pour l'entrée ET la sortie (conversion fréquence/canaux auto)."""
    if device is None:
        return None
    try:
        d = sd.query_devices(device)
        h = sd.query_hostapis()[d["hostapi"]]
        if "WASAPI" in h["name"]:
            return sd.WasapiSettings(auto_convert=True)
    except Exception:
        pass
    return None


# Alias sémantique pour la sortie (même logique WASAPI).
output_extra_settings = input_extra_settings
