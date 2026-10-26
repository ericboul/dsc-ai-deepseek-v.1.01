"""Applique un patch de configuration envoye par l'assistant (DCS-RYZEN-Copilote.exe).

L'assistant (GUI) ecrit un JSON temporaire puis appelle ce script avec le python
embarque : on reutilise ainsi dcs_config (valeurs par defaut, chemins) et apikeys
(fichier de cle par fournisseur) sans dupliquer la logique.

Usage : python\\python.exe eb_apply_setup.py C:\\...\\patch.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import apikeys  # noqa: E402
import dcs_config  # noqa: E402

PROVIDER_DEFAULTS = {
    "deepseek":  ("deepseek-chat", "https://api.deepseek.com/v1"),
    "openai":    ("gpt-4o-mini", "https://api.openai.com/v1"),
    "anthropic": ("claude-sonnet-4-6", ""),
    "ollama":    ("llama3.1", "http://localhost:11434/v1"),
    "custom":    ("", ""),
}


def apply(patch):
    cfg = dcs_config.load()
    prov = (patch.get("llm_provider") or cfg.get("llm_provider") or "deepseek").lower()
    dmodel, dbase = PROVIDER_DEFAULTS.get(prov, ("", ""))
    prev = cfg.get("llm_provider")
    cfg["llm_provider"] = prov
    cfg["llm_model"] = (patch.get("llm_model") or "").strip() or (
        dmodel if prev != prov or not cfg.get("llm_model") else cfg.get("llm_model"))
    cfg["llm_base_url"] = (patch.get("llm_base_url") or "").strip().rstrip("/") or dbase
    if prov in ("openai", "custom"):
        cfg["llm_api_key_env"] = "OPENAI_API_KEY"
    if prov == "anthropic":
        cfg["claude_model"] = cfg["llm_model"]

    if patch.get("mic_device_name") is not None:
        cfg["mic_device_name"] = patch.get("mic_device_name") or ""
        cfg["mic_device"] = patch.get("mic_device")
    if patch.get("ptt"):
        p = patch["ptt"]
        cfg["ptt"] = {"type": p.get("type", "keyboard"),
                      "key": p.get("key", "right ctrl"),
                      "label": p.get("label", p.get("key", "right ctrl"))}
    if patch.get("language"):
        cfg["language"] = patch["language"]
    if patch.get("whisper_model"):
        cfg["whisper_model"] = patch["whisper_model"]

    voice = (patch.get("voice") or "").strip()
    if voice:
        cfg["piper_model_path"] = voice
        for persona in cfg.get("personas", []):
            if persona.get("enabled", True):
                persona["voice"] = voice
    if patch.get("wizard_on_start") is not None:
        cfg["wizard_on_start"] = bool(patch["wizard_on_start"])

    dcs_config.save(cfg)

    key = (patch.get("api_key") or "").strip()
    if key and apikeys.needs_key(dict(cfg, llm_provider=prov)):
        apikeys.save_key(prov, key, cfg)
    return cfg


def main(argv):
    if len(argv) < 2:
        print("usage: eb_apply_setup.py patch.json")
        return 2
    with open(argv[1], "r", encoding="utf-8") as fh:
        patch = json.load(fh)
    cfg = apply(patch)
    print("config appliquee : %s / %s" % (cfg.get("llm_provider"), cfg.get("llm_model")))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main(sys.argv))
