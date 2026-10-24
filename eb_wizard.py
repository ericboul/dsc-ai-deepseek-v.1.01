"""DCS RYZEN Copilote — assistant de configuration puis démarrage du copilote.

Compilé en DCS-RYZEN-Copilote.exe et posé dans le dossier de l'application.
Au lancement :
  1. il lit config.json (valeurs pré-remplies) ;
  2. il demande la configuration : fournisseur IA + clé, micro, push-to-talk,
     voix, langue ;
  3. il enregistre (via le python embarqué : eb_apply_setup.py) ;
  4. il démarre le copilote (python\\python.exe app.py) et ouvre l'interface.

Options : --selftest (diagnostic texte, sans fenêtre), --silent (démarre
directement le copilote si la configuration est complète).
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import messagebox, ttk

APP_TITLE = "DCS RYZEN Copilote"
URL = "http://127.0.0.1:5001"
UI_PORT = 5001
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

PROVIDERS = [
    # (id stocké dans config.json, libellé, URL de base, modèle par défaut)
    ("deepseek", "DeepSeek (recommandé)", "", ""),
    ("openai", "OpenAI", "", ""),
    ("anthropic", "Anthropic (Claude)", "", ""),
    ("custom", "Personnalisé — URL + clé API", "", ""),
    ("custom", "Top Tools AI (top-tools-ai.com)", "https://top-tools-ai.com/api/v1", "Top-Tools-Ai"),
    ("custom", "OpenRouter (openrouter.ai)", "https://openrouter.ai/api/v1", ""),
    ("custom", "Mistral (api.mistral.ai)", "https://api.mistral.ai/v1", "mistral-large-latest"),
    ("ollama", "Ollama (local, sans clé)", "", ""),
]
MODEL_HINTS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-6",
    "ollama": "llama3.1",
    "custom": "",
}
BASE_HINTS = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}
LANGUAGES = [("fr", "Français"), ("en", "English"), ("de", "Deutsch"), ("es", "Español"),
             ("it", "Italiano"), ("nl", "Nederlands"), ("ru", "Русский")]
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
KEYMAP = {"Control_R": "right ctrl", "Control_L": "left ctrl",
          "Shift_R": "right shift", "Shift_L": "left shift",
          "Alt_R": "right alt", "Alt_L": "left alt", "space": "space",
          "Return": "enter", "Escape": "esc", "Tab": "tab",
          "Caps_Lock": "caps lock", "Prior": "page up", "Next": "page down",
          "Insert": "insert", "Delete": "delete", "Home": "home", "End": "end"}

BG = "#0f1419"
CARD = "#161d25"
FG = "#e6edf3"
MUTED = "#8b98a5"
ACCENT = "#2f81f7"


def app_root():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


ROOT = app_root()
PY = os.path.join(ROOT, "python", "python.exe")
CONFIG = os.path.join(ROOT, "config.json")


def port_open(port=UI_PORT):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def read_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def run_py(args, timeout=120, stdin_text=None):
    """Appelle le python embarqué (libs du dossier)."""
    return subprocess.run([PY] + args, cwd=ROOT, timeout=timeout,
                          input=stdin_text, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          creationflags=CREATE_NO_WINDOW)


def mic_list():
    code = ("import json,sounddevice as sd;"
            "print(json.dumps([{'i':i,'n':d['name']} for i,d in enumerate(sd.query_devices())"
            " if d['max_input_channels']>0]))")
    try:
        r = run_py(["-c", code], timeout=60)
        if r.returncode == 0:
            return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return []


def voice_list():
    d = os.path.join(ROOT, "piper", "voices")
    try:
        return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".onnx"))
    except Exception:
        return []


def dcs_bridge_ok():
    sg = os.path.join(os.path.expanduser("~"), "Saved Games", "DCS", "Scripts")
    return os.path.exists(os.path.join(sg, "dcs_claude_export.lua"))


def key_name(keysym):
    if keysym in KEYMAP:
        return KEYMAP[keysym]
    if len(keysym) > 1 and keysym[0] == "F" and keysym[1:].isdigit():
        return keysym.lower()
    return keysym.lower()


def start_copilot():
    subprocess.Popen([PY, os.path.join(ROOT, "app.py")], cwd=ROOT,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    for _ in range(40):
        if port_open():
            break
        threading.Event().wait(0.5)
    try:
        webbrowser.open(URL)
    except Exception:
        pass


class Wizard:
    def __init__(self, root):
        self.win = root
        self.cfg = read_config()
        self.patch = {}
        self.mics = []
        self.voices = voice_list()
        self.busy = False

        root.title(APP_TITLE + " — configuration")
        root.configure(bg=BG)
        root.geometry("700x790")
        root.minsize(660, 740)
        try:
            # icône de la fenêtre = logo de l'application (Le Lien Neural)
            ico = os.path.join(ROOT, "eb_logo.ico")
            if os.path.isfile(ico):
                root.iconbitmap(default=ico)
        except Exception:
            pass

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox", fieldbackground="#0b1017", background=CARD,
                        foreground=FG, arrowcolor=FG, selectbackground="#0b1017",
                        selectforeground=FG)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#0b1017"), ("!disabled", "#0b1017")],
                  foreground=[("readonly", FG), ("!disabled", FG)],
                  selectbackground=[("readonly", "#0b1017")],
                  selectforeground=[("readonly", FG)],
                  arrowcolor=[("!disabled", FG)])
        style.configure("Vertical.TScrollbar", background=CARD)
        # menus deroulants (listbox interne) : sinon texte blanc sur fond blanc
        root.option_add("*TCombobox*Listbox.background", "#0b1017")
        root.option_add("*TCombobox*Listbox.foreground", FG)
        root.option_add("*TCombobox*Listbox.selectBackground", "#243040")
        root.option_add("*TCombobox*Listbox.selectForeground", FG)

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=18, pady=(16, 6))
        tk.Label(head, text=APP_TITLE, bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(head, text="Configure une fois, puis le copilote démarre.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=6)

        # ---- Cerveau (IA)
        card1 = self._card(body, "Cerveau (IA)")
        grid = tk.Frame(card1, bg=CARD)
        grid.pack(fill="x", pady=(2, 0))
        grid.columnconfigure(1, weight=1)

        self.prov = tk.StringVar(value=(self.cfg.get("llm_provider") or "deepseek"))
        self.model = tk.StringVar(value=self.cfg.get("llm_model") or "")
        self.base = tk.StringVar(value=self.cfg.get("llm_base_url") or "")
        self.key = tk.StringVar(value="")

        self._label(grid, "Fournisseur", 0)
        self.prov_box = ttk.Combobox(grid, values=[p[1] for p in PROVIDERS],
                                     state="readonly", width=34)
        self.prov_box.current(self._initial_prov_index())
        self.prov_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.prov_box.bind("<<ComboboxSelected>>", self._on_prov)

        self._label(grid, "Modèle", 1)
        self.model_box = ttk.Combobox(grid, textvariable=self.model, values=[], width=30)
        self.model_box.grid(row=1, column=1, sticky="ew", pady=3)
        self._btn(grid, "Lister les modèles", self.list_models, secondary=True).grid(
            row=1, column=2, padx=(6, 0))

        self._label(grid, "URL API", 2)
        tk.Entry(grid, textvariable=self.base, bg="#0b1017", fg=FG, insertbackground=FG,
                 relief="flat").grid(row=2, column=1, sticky="ew", pady=3, ipady=3)

        self._label(grid, "Clé API", 3)
        self.key_entry = tk.Entry(grid, textvariable=self.key, show="•", bg="#0b1017", fg=FG,
                                  insertbackground=FG, relief="flat")
        self.key_entry.grid(row=3, column=1, sticky="ew", pady=3, ipady=3)

        self.key_state = tk.Label(card1, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 8))
        self.key_state.pack(anchor="w", pady=(4, 0))
        self._refresh_key_state()

        btns = tk.Frame(card1, bg=CARD)
        btns.pack(anchor="w", pady=(6, 0))
        self._btn(btns, "Tester la clé", self.test_key, secondary=True).pack(side="left")

        # ---- Micro & PTT
        card2 = self._card(body, "Micro et push-to-talk")
        g2 = tk.Frame(card2, bg=CARD)
        g2.pack(fill="x")
        g2.columnconfigure(1, weight=1)

        self.mic = tk.StringVar(value=self.cfg.get("mic_device_name") or "(micro par défaut)")
        self._label(g2, "Micro", 0)
        self.mic_box = ttk.Combobox(g2, textvariable=self.mic, values=[], width=34)
        self.mic_box.grid(row=0, column=1, sticky="ew", pady=3)

        self.ptt = tk.StringVar(value=(self.cfg.get("ptt") or {}).get("key", "right ctrl"))
        self._label(g2, "Push-to-talk", 1)
        self.ptt_btn = self._btn(g2, self._ptt_label(), self.capture_ptt, secondary=True)
        self.ptt_btn.grid(row=1, column=1, sticky="w", pady=3)

        # ---- Voix & langue
        card3 = self._card(body, "Voix et reconnaissance")
        g3 = tk.Frame(card3, bg=CARD)
        g3.pack(fill="x")
        g3.columnconfigure(1, weight=1)

        cur_voice = os.path.basename(self.cfg.get("piper_model_path") or "")
        self.voice = tk.StringVar(value=cur_voice[:-5] if cur_voice.endswith(".onnx") else
                                  (self.voices[0] if self.voices else ""))
        self._label(g3, "Voix", 0)
        voice_box = ttk.Combobox(g3, textvariable=self.voice, values=self.voices, width=34,
                                 state="readonly")
        voice_box.grid(row=0, column=1, sticky="ew", pady=3)
        if self.voice.get() in self.voices:
            voice_box.current(self.voices.index(self.voice.get()))
        self._btn(g3, "Écouter", self.play_voice, secondary=True).grid(row=0, column=2, padx=6)

        self.lang = tk.StringVar(value=dict(LANGUAGES).get(self.cfg.get("language") or "fr", "Français"))
        self._label(g3, "Langue parlée", 1)
        lang_box = ttk.Combobox(g3, textvariable=self.lang, values=[l[1] for l in LANGUAGES],
                                width=22, state="readonly")
        lang_box.grid(row=1, column=1, sticky="w", pady=3)
        lang_box.current([l[1] for l in LANGUAGES].index(self.lang.get())
                         if self.lang.get() in [l[1] for l in LANGUAGES] else 0)

        self.whisper = tk.StringVar(value=self.cfg.get("whisper_model") or "small")
        self._label(g3, "Modèle Whisper", 2)
        wh_box = ttk.Combobox(g3, textvariable=self.whisper, values=WHISPER_MODELS, width=22,
                              state="readonly")
        wh_box.grid(row=2, column=1, sticky="w", pady=3)
        wh_box.current(WHISPER_MODELS.index(self.whisper.get())
                       if self.whisper.get() in WHISPER_MODELS else 2)
        tk.Label(card3, text="small = rapide · medium = plus précis mais lent sur CPU",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")

        # ---- pied de page
        foot = tk.Frame(root, bg=BG)
        foot.pack(fill="x", padx=18, pady=(4, 12))

        self.ask_again = tk.BooleanVar(value=bool(self.cfg.get("wizard_on_start", True)))
        tk.Checkbutton(foot, text="Me redemander la configuration au prochain démarrage",
                       variable=self.ask_again, bg=BG, fg=MUTED, selectcolor=CARD,
                       activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 9)).pack(anchor="w")

        self.status = tk.Label(foot, text=self._dcs_line(), bg=BG, fg=MUTED,
                               font=("Segoe UI", 8), anchor="w", justify="left")
        self.status.pack(fill="x", pady=(6, 8))

        row = tk.Frame(foot, bg=BG)
        row.pack(fill="x")
        self.go_btn = self._btn(row, "Enregistrer et démarrer le copilote", self.save_and_start)
        self.go_btn.pack(side="left")
        self._btn(row, "Enregistrer seulement", self.save_only, secondary=True).pack(side="left", padx=8)
        self._btn(row, "Quitter", root.destroy, secondary=True).pack(side="right")

        root.protocol("WM_DELETE_WINDOW", root.destroy)
        threading.Thread(target=self._load_mics, daemon=True).start()

    # ---------- helpers UI
    def _card(self, parent, title):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground="#243040")
        card.pack(fill="x", pady=6)
        tk.Label(card, text=title, bg=CARD, fg="#9fc3ff",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        # les widgets sont ajoutés directement dans `card` par l'appelant
        return card

    def _label(self, parent, text, row):
        tk.Label(parent, text=text, bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)

    def _btn(self, parent, text, cmd, secondary=False):
        bg = "#1f2937" if secondary else ACCENT
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=FG,
                         activebackground="#2d3b4d", activeforeground=FG,
                         relief="flat", bd=0, padx=12, pady=7,
                         font=("Segoe UI", 9, "bold" if not secondary else "normal"),
                         cursor="hand2")

    def _prov_index(self, pid):
        for i, p in enumerate(PROVIDERS):
            if p[0] == pid:
                return i
        return 0

    def _initial_prov_index(self):
        """Retrouve l'entrée exacte : même id ET même URL de base si c'est un préréglage."""
        pid = self.prov.get()
        base = (self.base.get() or "").rstrip("/").lower()
        for i, p in enumerate(PROVIDERS):
            if p[0] == pid and p[2] and p[2].rstrip("/").lower() == base:
                return i
        return self._prov_index(pid)

    def _prov_id(self):
        return PROVIDERS[self.prov_box.current()][0]

    def _prov_entry(self):
        try:
            return PROVIDERS[self.prov_box.current()]
        except Exception:
            return PROVIDERS[0]

    def _on_prov(self, _evt=None):
        pid, _label, preset_base, preset_model = self._prov_entry()
        if preset_base or preset_model:
            # fournisseur prêt à l'emploi (Top Tools AI, OpenRouter, Mistral…)
            self.base.set(preset_base)
            self.model.set(preset_model)
        elif pid == "custom":
            # « Personnalisé » vierge : on ne garde pas les valeurs DeepSeek
            if "deepseek.com" in (self.base.get() or ""):
                self.base.set("")
            if (self.model.get() or "").strip() in ("deepseek-chat", "deepseek-reasoner"):
                self.model.set("")
        else:
            self.model.set(MODEL_HINTS.get(pid, ""))
            self.base.set(BASE_HINTS.get(pid, ""))
        self.key_entry.configure(state="disabled" if pid == "ollama" else "normal")
        self.key_state.configure(text=self._key_hint(pid))

    def list_models(self):
        """Interroge {URL}/models et propose les identifiants de modèles réels."""
        base = (self.base.get() or "").strip().rstrip("/")
        if not base.lower().startswith("http"):
            messagebox.showwarning(APP_TITLE, "Renseigne d'abord l'URL de base "
                                              "(ex. https://top-tools-ai.com/api/v1).")
            return
        key = (self.key.get() or "").strip()
        if not key:
            try:
                key = self._existing_key()
            except Exception:
                key = ""

        def work():
            req = urllib.request.Request(base + "/models",
                                         headers={"Authorization": "Bearer " + key,
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            items = data.get("data") if isinstance(data, dict) else data
            ids = []
            for it in items or []:
                mid = it.get("id") if isinstance(it, dict) else str(it)
                if mid:
                    ids.append(mid)
            if not ids:
                raise RuntimeError("aucun modèle renvoyé par %s/models" % base)

            def show():
                self.model_box.configure(values=ids)
                if self.model.get() not in ids:
                    self.model.set(ids[0])
                self.model_box.focus_set()
                self.status.configure(text="%d modèles disponibles — choisis dans la liste." % len(ids))
            self.win.after(0, show)

        self._run_bg(work, "liste des modèles récupérée.")

    def _existing_key(self):
        try:
            sys.path.insert(0, ROOT)
            import apikeys
            return apikeys.current_key(self._prov_id(), self.cfg) or ""
        except Exception:
            return ""

    def _ptt_label(self):
        return "Appuyer ici puis taper la touche — " + self.ptt.get()

    def _dcs_line(self):
        ok = dcs_bridge_ok()
        return ("Pont DCS : installé ✓" if ok else "Pont DCS : ABSENT — lance INSTALLER-TOUT.bat")

    def _refresh_key_state(self):
        self.key_state.configure(text=self._key_hint())

    def _key_hint(self, pid=None):
        pid = pid or self._prov_id()
        if pid == "ollama":
            return "Aucune clé nécessaire : Ollama tourne en local."
        if pid == "custom":
            return ("Personnalisé : URL de base (ex. https://api.mistral.ai/v1), "
                    "nom exact du modèle, puis la clé API.")
        try:
            sys.path.insert(0, ROOT)
            import apikeys
            k = apikeys.current_key(pid, self.cfg)
        except Exception:
            k = None
        if k:
            return "Clé enregistrée : " + (k[:3] + "…" + k[-4:] if len(k) > 8 else "oui")
        return "Aucune clé enregistrée pour ce fournisseur."

    def _load_mics(self):
        self.mics = mic_list()
        names = ["(micro par défaut)"] + [m["n"] for m in self.mics]
        saved = self.cfg.get("mic_device_name") or ""
        if saved and saved not in names:
            names.insert(1, saved)   # micro enregistré mais absent de l'énumération

        def apply():
            self.mic_box.configure(values=names)
            if self.mic.get() in names:
                self.mic_box.current(names.index(self.mic.get()))
            elif saved:
                self.mic.set(saved)
                self.mic_box.set(saved)
            else:
                self.mic_box.current(0)
        self.win.after(0, apply)

    # ---------- actions
    def capture_ptt(self):
        self.ptt_btn.configure(text="Appuie sur une touche…", bg="#334155")

        def on_key(evt):
            self.ptt.set(key_name(evt.keysym))
            self.ptt_btn.configure(text=self._ptt_label(), bg="#1f2937")
            self.win.unbind("<KeyPress>")
            return "break"

        self.win.bind("<KeyPress>", on_key)

    def play_voice(self):
        name = self.voice.get()
        if not name:
            return
        piper = os.path.join(ROOT, "piper", "piper", "piper.exe")
        model = os.path.join(ROOT, "piper", "voices", name + ".onnx")
        if not (os.path.exists(piper) and os.path.exists(model)):
            messagebox.showwarning(APP_TITLE, "Voix ou moteur Piper introuvable.")
            return
        out = os.path.join(tempfile.gettempdir(), "eb_voice_preview.wav")
        try:
            subprocess.run([piper, "-m", model, "-f", out],
                           input=b"Bonjour, je suis ton copilote DCS.",
                           creationflags=CREATE_NO_WINDOW, timeout=120)
            import winsound
            winsound.PlaySound(out, winsound.SND_FILENAME)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, "Lecture impossible : %s" % exc)

    def _collect(self):
        mic_name = self.mic.get()
        mic_idx = None
        for m in self.mics:
            if m["n"] == mic_name:
                mic_idx = m["i"]
                break
        lang_code = "fr"
        for code, label in LANGUAGES:
            if label == self.lang.get():
                lang_code = code
        voice_path = ""
        if self.voice.get():
            voice_path = os.path.join(ROOT, "piper", "voices", self.voice.get() + ".onnx")
        return {
            "llm_provider": self._prov_id(),
            "llm_model": self.model.get().strip(),
            "llm_base_url": self.base.get().strip(),
            "api_key": self.key.get().strip(),
            "mic_device_name": "" if mic_name.startswith("(") else mic_name,
            "mic_device": mic_idx,
            "ptt": {"type": "keyboard", "key": self.ptt.get(), "label": self.ptt.get()},
            "language": lang_code,
            "whisper_model": self.whisper.get(),
            "voice": voice_path,
            "wizard_on_start": not self.ask_again.get(),
        }

    def _apply(self):
        patch = self._collect()
        if patch["llm_provider"] == "custom":
            if not (patch["llm_base_url"] or "").lower().startswith("http"):
                raise RuntimeError("Fournisseur personnalisé : renseigne l'URL de base "
                                   "(ex. https://api.mistral.ai/v1).")
            if not (patch["llm_model"] or "").strip():
                raise RuntimeError("Fournisseur personnalisé : renseigne le nom exact du modèle "
                                   "(ex. mistral-large-latest).")
        fd, tmp = tempfile.mkstemp(suffix=".json", prefix="ebsetup_")
        os.close(fd)
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(patch, fh, ensure_ascii=False)
            r = run_py([os.path.join(ROOT, "eb_apply_setup.py"), tmp], timeout=180)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
        if r.returncode != 0:
            raise RuntimeError((r.stdout or "") + (r.stderr or ""))
        self.cfg = read_config()
        self._refresh_key_state()
        return patch

    def _run_bg(self, fn, done_text):
        if self.busy:
            return
        self.busy = True
        self.status.configure(text="…")
        self.go_btn.configure(state="disabled")

        def work():
            err = None
            try:
                fn()
            except Exception as exc:
                err = str(exc)
            def finish():
                self.busy = False
                self.go_btn.configure(state="normal")
                self.status.configure(text=("Erreur : " + err[:300]) if err else done_text)
                if err:
                    messagebox.showerror(APP_TITLE, err[:800])
            self.win.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def test_key(self):
        def work():
            self._apply()
            r = run_py([os.path.join(ROOT, "eb_check_llm.py")], timeout=120)
            out = (r.stdout or r.stderr or "").strip()
            if r.returncode != 0:
                raise RuntimeError(out or "échec du test")
        self._run_bg(work, "Clé OK — l'IA a répondu.")

    def save_only(self):
        self._run_bg(self._apply, "Configuration enregistrée.")

    def save_and_start(self):
        if port_open():
            webbrowser.open(URL)
            self.win.destroy()
            return

        def work():
            self._apply()
            self.win.after(0, self._start_then_close)

        self._run_bg(work, "Configuration enregistrée — démarrage du copilote…")

    def _start_then_close(self):
        try:
            start_copilot()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, "Démarrage impossible : %s" % exc)
            return
        self.win.destroy()


def selftest():
    lines = []
    def out(t):
        lines.append(str(t))
    out("root      : %s" % ROOT)
    out("python    : %s %s" % (PY, os.path.exists(PY)))
    out("app.py    : %s" % os.path.exists(os.path.join(ROOT, "app.py")))
    out("config    : %s" % os.path.exists(CONFIG))
    out("voix      : %d" % len(voice_list()))
    out("micros    : %d" % len(mic_list()))
    out("pont DCS  : %s" % dcs_bridge_ok())
    ok = os.path.exists(PY) and os.path.exists(os.path.join(ROOT, "app.py"))
    out("SELFTEST %s" % ("OK" if ok else "ECHEC"))
    # l'exe est compile sans console : le resultat doit atterrir dans un fichier
    try:
        with open(os.path.join(ROOT, "EB-selftest.log"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass
    try:
        print("\n".join(lines))
    except Exception:
        pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if not os.path.exists(PY):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_TITLE,
                             "python\\python.exe est absent.\n\n"
                             "Lance d'abord INSTALLER-TOUT.bat dans :\n" + ROOT)
        return 1
    if "--silent" in sys.argv:
        start_copilot()
        return 0
    root = tk.Tk()
    Wizard(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
