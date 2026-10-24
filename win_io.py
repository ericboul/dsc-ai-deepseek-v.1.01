"""Injection clavier Windows + détection de la fenêtre DCS.

Le copilote « appuie » sur les touches de l'avion via SendInput en codes
SCAN (ce que lit DirectInput, donc DCS). Sécurité : on n'envoie rien si la
fenêtre DCS n'est pas au premier plan (sinon on écrirait dans Discord/Word).

Aucune dépendance : ctypes uniquement.
"""
import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------- SendInput
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VSC_TO_VK = 1


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _send(scan, extended=False, up=False):
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if up:
        flags |= KEYEVENTF_KEYUP
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp.ki = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ---------------------------------------------------------------- touches DCS
# nom de touche DCS -> (code scan, étendu)
_SCAN = {
    "ESC": (0x01, False), "ESCAPE": (0x01, False),
    "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False),
    "5": (0x06, False), "6": (0x07, False), "7": (0x08, False), "8": (0x09, False),
    "9": (0x0A, False), "0": (0x0B, False),
    "-": (0x0C, False), "=": (0x0D, False), "BACK": (0x0E, False),
    "BACKSPACE": (0x0E, False), "TAB": (0x0F, False),
    "Q": (0x10, False), "W": (0x11, False), "E": (0x12, False), "R": (0x13, False),
    "T": (0x14, False), "Y": (0x15, False), "U": (0x16, False), "I": (0x17, False),
    "O": (0x18, False), "P": (0x19, False), "[": (0x1A, False), "]": (0x1B, False),
    "ENTER": (0x1C, False), "RETURN": (0x1C, False),
    "LCTRL": (0x1D, False), "RCTRL": (0x1D, True),
    "A": (0x1E, False), "S": (0x1F, False), "D": (0x20, False), "F": (0x21, False),
    "G": (0x22, False), "H": (0x23, False), "J": (0x24, False), "K": (0x25, False),
    "L": (0x26, False), ";": (0x27, False), "'": (0x28, False), "`": (0x29, False),
    "LSHIFT": (0x2A, False), "\\": (0x2B, False),
    "Z": (0x2C, False), "X": (0x2D, False), "C": (0x2E, False), "V": (0x2F, False),
    "B": (0x30, False), "N": (0x31, False), "M": (0x32, False),
    ",": (0x33, False), ".": (0x34, False), "/": (0x35, False),
    "RSHIFT": (0x36, False),
    "NUM*": (0x37, False), "LALT": (0x38, False), "SPACE": (0x39, False),
    "CAPSLOCK": (0x3A, False),
    "F1": (0x3B, False), "F2": (0x3C, False), "F3": (0x3D, False), "F4": (0x3E, False),
    "F5": (0x3F, False), "F6": (0x40, False), "F7": (0x41, False), "F8": (0x42, False),
    "F9": (0x43, False), "F10": (0x44, False),
    "NUMLOCK": (0x45, False), "SCROLLLOCK": (0x46, False),
    "NUM7": (0x47, False), "NUM8": (0x48, False), "NUM9": (0x49, False),
    "NUM-": (0x4A, False), "NUM4": (0x4B, False), "NUM5": (0x4C, False),
    "NUM6": (0x4D, False), "NUM+": (0x4E, False), "NUM1": (0x4F, False),
    "NUM2": (0x50, False), "NUM3": (0x51, False), "NUM0": (0x52, False),
    "NUM.": (0x53, False),
    "F11": (0x57, False), "F12": (0x58, False),
    "HOME": (0x47, True), "UP": (0x48, True), "PAGEUP": (0x49, True),
    "LEFT": (0x4B, True), "RIGHT": (0x4D, True), "END": (0x4F, True),
    "DOWN": (0x50, True), "PAGEDOWN": (0x51, True), "INSERT": (0x52, True),
    "DELETE": (0x53, True),
    "LWIN": (0x5B, True), "RWIN": (0x5C, True), "APPS": (0x5D, True),
    "NUM/": (0x35, True), "NUMENTER": (0x1C, True), "RALT": (0x38, True),
    "PRINTSCREEN": (0x37, True), "PAUSE": (0x45, True),
    "OEM102": (0x56, False),
}
_ALIASES = {
    "LEFT CTRL": "LCTRL", "RIGHT CTRL": "RCTRL", "LEFT SHIFT": "LSHIFT",
    "RIGHT SHIFT": "RSHIFT", "LEFT ALT": "LALT", "RIGHT ALT": "RALT",
    "ESCAPE": "ESC", "RETURN": "ENTER", "BACKSPACE": "BACK",
    "PAGE UP": "PAGEUP", "PAGE DOWN": "PAGEDOWN", "DEL": "DELETE",
    "INS": "INSERT", "NUMDEC": "NUM.", "NUMPERIOD": "NUM.",
    "MINUS": "-", "EQUALS": "=", "SEMICOLON": ";", "APOSTROPHE": "'",
    "GRAVE": "`", "BACKSLASH": "\\", "COMMA": ",", "PERIOD": ".",
    "SLASH": "/", "LBRACKET": "[", "RBRACKET": "]",
}


def scan_of(key):
    """(code scan, étendu) pour un nom de touche DCS, ou None."""
    if not key:
        return None
    k = str(key).strip().upper()
    k = _ALIASES.get(k, k)
    return _SCAN.get(k)


# ---------------------------------------------------------------- fenêtre DCS
_DCS_EXE = ("dcs.exe", "dcs_server.exe", "dcs_updater.exe")


def _window_text(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _exe_of(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def dcs_window():
    """Handle de la fenêtre principale de DCS, ou None."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if not title:
            return True
        exe = _exe_of(_pid_of(hwnd))
        base = exe.rsplit("\\", 1)[-1]
        if base in _DCS_EXE or "digital combat simulator" in title.lower():
            if user32.GetWindow(hwnd, 4) == 0:      # GW_OWNER == 0 -> fenêtre principale
                found.append(hwnd)
        return True

    user32.EnumWindows(_cb, 0)
    return found[0] if found else None


def foreground_window():
    return user32.GetForegroundWindow()


def is_foreground(hwnd):
    return bool(hwnd) and foreground_window() == hwnd


def focus(hwnd):
    """Met la fenêtre DCS au premier plan (best effort)."""
    if not hwnd:
        return False
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.12)
    except Exception:
        pass
    return is_foreground(hwnd)


# ---------------------------------------------------------------- envoi
def press_keys(mods, key, hold=0.05, ensure_focus=True):
    """Appuie sur combinaison (modificateurs + touche) et relâche.

    Renvoie {ok: bool, error: str|None, window: bool}.
    """
    target = scan_of(key)
    if not target:
        return {"ok": False, "error": "touche inconnue: %s" % key}
    mod_scans = []
    for m in mods or []:
        s = scan_of(m)
        if s:
            mod_scans.append(s)
    hwnd = dcs_window()
    if ensure_focus:
        if not hwnd:
            return {"ok": False, "window": False,
                    "error": "fenêtre DCS introuvable : lance DCS avant"}
        if not is_foreground(hwnd) and not focus(hwnd):
            return {"ok": False, "window": False,
                    "error": "DCS n'est pas au premier plan"}
    for scan, ext in mod_scans:
        _send(scan, ext, up=False)
        time.sleep(0.012)
    _send(target[0], target[1], up=False)
    time.sleep(hold)
    _send(target[0], target[1], up=True)
    for scan, ext in reversed(mod_scans):
        time.sleep(0.012)
        _send(scan, ext, up=True)
    return {"ok": True, "error": None, "window": bool(hwnd)}


def release_modifiers():
    """Relâche les modificateurs (au cas où un envoi aurait été interrompu)."""
    for name in ("LCTRL", "RCTRL", "LSHIFT", "RSHIFT", "LALT", "RALT", "LWIN", "RWIN"):
        s = scan_of(name)
        if s:
            _send(s[0], s[1], up=True)


def dcs_running():
    return dcs_window() is not None
