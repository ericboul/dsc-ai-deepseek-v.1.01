"""
Point d'entrée UNIQUE de DCS RYZEN Copilote.

Lance en même temps :
  - l'interface web de configuration (http://127.0.0.1:5001), et
  - la boucle du copilote,
qui partagent la même config en mémoire (core.py) -> réglages à la volée.

Lancé par run.bat.
"""
import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import socket
import sys
import threading
import webbrowser

import core
import configurator
import copilot

URL = "http://127.0.0.1:5001"
LOCK_PORT = 5099          # verrou "une seule instance"
_LOCK = None


def _single_instance():
    """Empêche deux copilotes en même temps (sinon ports 5001/5010 partagés
    et télémétrie DCS livrée à l'instance au hasard)."""
    global _LOCK
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        print("Le copilote tourne deja : ouverture de l'interface existante.")
        try:
            webbrowser.open(URL)
        except Exception:
            pass
        sys.exit(0)
    _LOCK = s


def _serve():
    # Journal silencieux : les sondages de l'interface (plusieurs par seconde)
    # noyaient la console. On ne garde que les avertissements et les erreurs.
    import logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    # use_reloader=False : indispensable hors du thread principal.
    configurator.app.run(host="127.0.0.1", port=5001, threaded=True, use_reloader=False)


def main():
    _single_instance()
    # Charge la clé API du fournisseur courant (fichier -> variable d'env).
    import apikeys
    _cfg = core.get_config()
    apikeys.load_into_env(_cfg.get("llm_provider", "deepseek"), _cfg)
    # Interface web en tâche de fond.
    threading.Thread(target=_serve, daemon=True).start()
    # Précharge Whisper (pas d'attente au 1er test / 1re phrase).
    threading.Thread(target=core.preload_whisper, daemon=True).start()
    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    print(f"Interface de configuration : {URL}")
    # Boucle du copilote sur le thread principal (clavier/audio globaux).
    copilot.run_copilot()


if __name__ == "__main__":
    main()
