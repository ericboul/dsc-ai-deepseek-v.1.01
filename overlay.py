"""Carré de touche à l'écran (Win32 pur, sans tkinter).

Le python embarqué de l'application n'a pas tkinter : cette version dessine la
fenêtre avec l'API Windows (GDI) via ctypes. Fenêtre sans bordure, toujours
au-dessus, qui laisse passer les clics et ne prend jamais le focus — on peut
continuer à piloter pendant qu'elle s'affiche.

Utilisation :
    ov = KeyOverlay()
    ov.show("MAJ+G", "TRAIN - SORTIR", seconds=6, note="Left Vertical Panel")
    ov.close()
"""
import ctypes
import ctypes.wintypes as wt
import queue
import threading
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002

WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_DESTROY = 0x0002

DT_LEFT = 0x00000000
DT_CENTER = 0x00000001
DT_VCENTER = 0x00000004
DT_WORDBREAK = 0x00000010
DT_NOPREFIX = 0x00000800

LWA_ALPHA = 0x00000002
DEFAULT_CHARSET = 1
FW_BOLD = 700
CLEARTYPE_QUALITY = 5
TRANSPARENT_BG = 1
NULL_BRUSH_ID = 5

# couleurs (BGR pour COLORREF)
C_BG = 0x140F0B          # #0b0f14
C_BORDER = 0xFFD039      # #39d0ff
C_KEYBG = 0x30241B       # #1b2430
C_WHITE = 0xFFFFFF
C_LABEL = 0xE2D6C9       # #c9d6e2
C_WARN = 0x4DCEFF        # #ffcf4d

# --- prototypes : sans eux, ctypes tronque les handles (OverflowError) ----
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE,
                                   ctypes.c_void_p]
user32.CreateWindowExW.restype = wt.HWND
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.BeginPaint.argtypes = [wt.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = wt.HDC
user32.EndPaint.argtypes = [wt.HWND, ctypes.c_void_p]
user32.FillRect.argtypes = [wt.HDC, ctypes.c_void_p, wt.HBRUSH]
user32.DrawTextW.argtypes = [wt.HDC, wt.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wt.UINT]
user32.DrawTextW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT, wt.UINT]
user32.MoveWindow.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, wt.BOOL]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.DWORD, ctypes.c_byte, wt.DWORD]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.LoadCursorW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
user32.LoadCursorW.restype = wt.HANDLE
gdi32.CreateSolidBrush.argtypes = [wt.DWORD]
gdi32.CreateSolidBrush.restype = wt.HBRUSH
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.CreatePen.restype = wt.HANDLE
gdi32.SelectObject.argtypes = [wt.HDC, wt.HANDLE]
gdi32.SelectObject.restype = wt.HANDLE
gdi32.CreateFontW.restype = wt.HANDLE
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = wt.HANDLE
gdi32.Rectangle.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wt.HDC, wt.DWORD]
gdi32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.DeleteObject.argtypes = [wt.HANDLE]

IDC_ARROW = ctypes.cast(32512, wt.LPCWSTR)

W, H = 460, 168
CLASS_NAME = "DcsRyzenKeyBox"


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
                ("hIconSm", wt.HICON)]


class _PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", wt.HDC), ("fErase", wt.BOOL),
                ("rcPaint", _RECT), ("fRestore", wt.BOOL),
                ("fIncUpdate", wt.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


class KeyOverlay:
    """Carré de touche : API show/hide/close, 100 % Win32."""

    def __init__(self, seconds=6.0, position="bottom"):
        self.seconds = float(seconds)
        self.position = position
        self._q = queue.Queue()
        self._hwnd = None
        self._alive = True
        self._deadline = 0.0
        self._content = ("", "", "", C_BORDER)
        self._fonts = {}
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(3.0)

    # ------------------------------------------------------------------ API
    def show(self, key_text, label, seconds=None, note="", color=None):
        self._q.put(("show", key_text, label, seconds or self.seconds, note, color))

    def hide(self):
        self._q.put(("hide",))

    def close(self):
        self._q.put(("quit",))
        self._alive = False

    def visible(self):
        try:
            return bool(self._hwnd) and bool(user32.IsWindowVisible(self._hwnd))
        except Exception:
            return False

    # ------------------------------------------------------------------ Win32
    def _run(self):
        try:
            hinst = kernel32.GetModuleHandleW(None)
            wc = _WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(_WNDCLASSEXW)
            wc.style = 0
            self._proc = WNDPROC(self._wndproc)      # garder la référence vivante
            wc.lpfnWndProc = self._proc
            wc.hInstance = hinst
            wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)   # IDC_ARROW
            wc.hbrBackground = gdi32.CreateSolidBrush(C_BG)
            wc.lpszClassName = CLASS_NAME
            user32.RegisterClassExW(ctypes.byref(wc))         # déjà enregistrée : ok

            self._hwnd = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT |
                WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                CLASS_NAME, "DCS RYZEN Copilote - touche", WS_POPUP,
                0, 0, W, H, None, None, hinst, None)
            if not self._hwnd:
                self._ready.set()
                return
            user32.SetLayeredWindowAttributes(self._hwnd, 0, 235, LWA_ALPHA)
            self._fonts = {
                "key": gdi32.CreateFontW(34, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET,
                                         0, 0, CLEARTYPE_QUALITY, 0, "Consolas"),
                "key_s": gdi32.CreateFontW(21, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET,
                                           0, 0, CLEARTYPE_QUALITY, 0, "Consolas"),
                "label": gdi32.CreateFontW(19, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET,
                                           0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI"),
                "note": gdi32.CreateFontW(15, 0, 0, 0, 400, 0, 0, 0, DEFAULT_CHARSET,
                                          0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI"),
            }
            self._ready.set()
            msg = wt.MSG()
            while self._alive:
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                self._pump()
                if self._deadline and time.time() > self._deadline:
                    self._hide()
                time.sleep(0.03)
            user32.DestroyWindow(self._hwnd)
        except Exception:
            self._ready.set()

    def _pump(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "show":
                    _, key_text, label, secs, note, color = msg
                    self._content = (key_text, label, note, color or C_BORDER)
                    self._place()
                    user32.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOACTIVATE | SWP_NOSIZE | SWP_NOMOVE)
                    user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
                    user32.InvalidateRect(self._hwnd, None, True)
                    user32.UpdateWindow(self._hwnd)
                    self._deadline = time.time() + float(secs)
                elif msg[0] == "hide":
                    self._hide()
                elif msg[0] == "quit":
                    self._alive = False
        except queue.Empty:
            pass

    def _hide(self):
        try:
            user32.ShowWindow(self._hwnd, SW_HIDE)
        except Exception:
            pass
        self._deadline = 0.0

    def _place(self):
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = max(0, (sw - W) // 2)
        y = sh - H - 90 if self.position == "bottom" else (sh - H) // 3
        user32.MoveWindow(self._hwnd, x, y, W, H, True)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_PAINT:
                self._paint(hwnd)
                return 0
            if msg == WM_ERASEBKGND:
                return 1
            if msg == WM_DESTROY:
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------------ dessin
    def _paint(self, hwnd):
        ps = _PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        try:
            key_text, label, note, color = self._content
            rc = _RECT(0, 0, W, H)
            br_bg = gdi32.CreateSolidBrush(C_BG)
            user32.FillRect(hdc, ctypes.byref(rc), br_bg)
            gdi32.DeleteObject(br_bg)

            pen = gdi32.CreatePen(0, 2, color)
            old_pen = gdi32.SelectObject(hdc, pen)
            old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH_ID))
            gdi32.Rectangle(hdc, 1, 1, W - 1, H - 1)

            # carré de la touche
            kx0, ky0, kx1, ky1 = 18, 22, 154, 144
            br_key = gdi32.CreateSolidBrush(C_KEYBG)
            gdi32.SelectObject(hdc, br_key)
            gdi32.Rectangle(hdc, kx0, ky0, kx1, ky1)
            gdi32.DeleteObject(br_key)

            gdi32.SetBkMode(hdc, TRANSPARENT_BG)
            old_font = gdi32.SelectObject(
                hdc, self._fonts["key"] if len(key_text) <= 5 else self._fonts["key_s"])
            gdi32.SetTextColor(hdc, C_WHITE)
            r = _RECT(kx0 + 4, ky0 + 4, kx1 - 4, ky1 - 4)
            buf = ctypes.create_unicode_buffer(key_text)
            user32.DrawTextW(hdc, buf, -1, ctypes.byref(r),
                             DT_CENTER | DT_VCENTER | DT_WORDBREAK | DT_NOPREFIX)

            gdi32.SelectObject(hdc, self._fonts["label"])
            gdi32.SetTextColor(hdc, C_LABEL)
            r2 = _RECT(174, 40, W - 16, 124)
            buf2 = ctypes.create_unicode_buffer(label)
            user32.DrawTextW(hdc, buf2, -1, ctypes.byref(r2),
                             DT_LEFT | DT_WORDBREAK | DT_NOPREFIX)

            if note:
                gdi32.SelectObject(hdc, self._fonts["note"])
                gdi32.SetTextColor(hdc, C_WARN)
                r3 = _RECT(174, 120, W - 16, H - 10)
                buf3 = ctypes.create_unicode_buffer(note)
                user32.DrawTextW(hdc, buf3, -1, ctypes.byref(r3),
                                 DT_LEFT | DT_WORDBREAK | DT_NOPREFIX)

            gdi32.SelectObject(hdc, old_font)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(pen)
        finally:
            user32.EndPaint(hwnd, ctypes.byref(ps))
