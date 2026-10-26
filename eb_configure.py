"""Configure le fournisseur LLM de DCS RYZEN Copilote (stdlib uniquement).

Appele par eb_install.ps1, ou a la main :
  python\\python.exe eb_configure.py --provider deepseek --key sk-xxxx
  python\\python.exe eb_configure.py --provider ollama --model llama3.1
  python\\python.exe eb_configure.py --show

Ecrit :
  - config.json          (llm_provider / llm_model / llm_base_url / llm_api_key_env)
  - deepseek_key.txt | openai_key.txt | apikey.txt   (la cle, sans retour ligne)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import apikeys  # noqa: E402
import dcs_config  # noqa: E402

PROVIDERS = {
    "deepseek":  {"model": "deepseek-chat",            "base": "https://api.deepseek.com/v1", "label": "DeepSeek"},
    "openai":    {"model": "gpt-4o-mini",              "base": "https://api.openai.com/v1",   "label": "OpenAI"},
    "anthropic": {"model": "claude-sonnet-4-6",        "base": "",                            "label": "Anthropic"},
    "ollama":    {"model": "llama3.1",                 "base": "http://localhost:11434/v1",   "label": "Ollama (local)"},
    "custom":    {"model": "",                          "base": "",                            "label": "API compatible OpenAI"},
    "flm":       {"model": "qwen3.5:4b",                "base": "http://127.0.0.1:52625/v1",   "label": "FastFlowLM (NPU local)"},
    "lmstudio":  {"model": "",                          "base": "http://127.0.0.1:1234/v1",    "label": "LM Studio (local)"},
}


def show():
    cfg = dcs_config.load()
    prov = cfg.get("llm_provider", "deepseek")
    key = apikeys.current_key(prov, cfg)
    print(f"Fournisseur : {prov}")
    print(f"Modele      : {cfg.get('llm_model') or '(defaut)'}")
    print(f"URL API     : {cfg.get('llm_base_url') or '(defaut)'}")
    print(f"Cle API     : {apikeys.masked(key) if key else '(aucune)'}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--key-file", default="", help="lit la cle dans un fichier")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args(argv)

    if a.show:
        show()
        return 0

    prov = (a.provider or "").strip().lower()
    if prov not in PROVIDERS:
        print("fournisseur inconnu : %s (attendu : %s)" % (prov, ", ".join(PROVIDERS)))
        return 2

    cfg = dcs_config.load()
    info = PROVIDERS[prov]
    prev = cfg.get("llm_provider", "deepseek")
    cfg["llm_provider"] = prov
    if a.model.strip():
        cfg["llm_model"] = a.model.strip()
    elif prev != prov or not cfg.get("llm_model"):
        cfg["llm_model"] = info["model"]
    if a.base_url.strip():
        cfg["llm_base_url"] = a.base_url.strip().rstrip("/")
    else:
        cfg.setdefault("llm_base_url", "")
        if prov in ("deepseek", "openai", "ollama"):
            cfg["llm_base_url"] = info["base"]
    if prov == "anthropic":
        cfg["claude_model"] = cfg.get("llm_model") or info["model"]
    if prov in ("openai", "custom"):
        cfg["llm_api_key_env"] = "OPENAI_API_KEY"

    dcs_config.save(cfg)

    key = (a.key or "").strip()
    if a.key_file:
        with open(a.key_file, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
    if prov == "ollama":
        print("Fournisseur : ollama (aucune cle requise)")
    elif key:
        apikeys.save_key(prov, key, cfg)
        print("Fournisseur : %s | modele %s | cle %s" % (prov, cfg.get("llm_model"), apikeys.masked(key)))
    else:
        cur = apikeys.current_key(prov, cfg)
        if cur:
            print("Fournisseur : %s | modele %s | cle deja enregistree %s" % (prov, cfg.get("llm_model"), apikeys.masked(cur)))
        else:
            print("Fournisseur : %s | modele %s | cle absente (a saisir dans l'interface)" % (prov, cfg.get("llm_model")))
    return 0


if __name__ == "__main__":
    # force l'encodage utf-8 pour les accents des messages
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
