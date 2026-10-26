"""Teste la connexion au fournisseur LLM configure (utilise libs\\ + config.json).

Sortie 0 = OK, 1 = echec. Appele par eb_install.ps1 et par le bouton
"Tester la connexion" de l'interface (qui a son propre test).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import apikeys  # noqa: E402
import dcs_config  # noqa: E402
import llm  # noqa: E402


def main():
    cfg = dcs_config.load()
    prov = cfg.get("llm_provider", "deepseek")
    key = apikeys.load_into_env(prov, cfg)
    if apikeys.needs_key(cfg) and not key:
        print("ECHEC: aucune cle API pour %s." % prov)
        return 1
    if not apikeys.needs_key(cfg):
        print("fournisseur local (%s) : aucune cle requise" % prov)
    try:
        client = llm.make_client(cfg)
        text, _ = client.converse(
            "Tu es un test de connexion. Reponds uniquement: OK",
            [], [], "Dis OK.", lambda name, args: {})
    except Exception as e:
        msg = str(e)[:300]
        print("ECHEC: %s: %s" % (type(e).__name__, msg))
        return 1
    print("OK: reponse du modele -> %s" % (text or "(vide)").strip()[:120])
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
