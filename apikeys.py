"""Gestion des clés API par fournisseur (stockage fichier + variable d'env).

- DeepSeek   -> deepseek_key.txt  (var DEEPSEEK_API_KEY)
- Anthropic  -> apikey.txt        (var ANTHROPIC_API_KEY)
- OpenAI     -> openai_key.txt    (var OPENAI_API_KEY, ou cfg.llm_api_key_env)
- Ollama     -> aucune clé

La clé n'est affichée que masquée (3 premiers + 4 derniers caractères).
"""
import os

import dcs_config


LOCAL_PROVIDERS = ("ollama", "flm", "lmstudio")


def env_var(provider, cfg=None):
    if provider in LOCAL_PROVIDERS:
        return None
    if provider == "deepseek":
        return "DEEPSEEK_API_KEY"
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider == "ollama":
        return None
    return (cfg or {}).get("llm_api_key_env") or "OPENAI_API_KEY"


def key_file(provider):
    if provider in LOCAL_PROVIDERS:
        return None
    if provider == "deepseek":
        return os.path.join(dcs_config.HERE, "deepseek_key.txt")
    if provider == "anthropic":
        return os.path.join(dcs_config.HERE, "apikey.txt")
    if provider == "ollama":
        return None
    return os.path.join(dcs_config.HERE, "openai_key.txt")


def current_key(provider, cfg=None):
    """Clé courante : variable d'env sinon fichier. None si absente."""
    ev = env_var(provider, cfg)
    if ev and os.environ.get(ev):
        return os.environ[ev].strip()
    f = key_file(provider)
    if f and os.path.isfile(f):
        try:
            k = open(f, encoding="utf-8").read().strip()
            return k or None
        except Exception:
            return None
    return None


def load_into_env(provider, cfg=None):
    """Charge la clé du fichier dans la variable d'env si pas déjà définie."""
    ev = env_var(provider, cfg)
    if not ev or os.environ.get(ev):
        return os.environ.get(ev) if ev else None
    f = key_file(provider)
    if f and os.path.isfile(f):
        k = open(f, encoding="utf-8").read().strip()
        if k:
            os.environ[ev] = k
            return k
    return None


def save_key(provider, key, cfg=None):
    """Écrit la clé dans le fichier du fournisseur et l'applique à la variable d'env."""
    key = (key or "").strip()
    f = key_file(provider)
    if not f:
        raise ValueError("ce fournisseur ne nécessite pas de clé")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(key)
    ev = env_var(provider, cfg)
    if ev:
        os.environ[ev] = key


def masked(key):
    if not key:
        return ""
    k = key.strip()
    if len(k) <= 8:
        return "•" * len(k)
    return k[:3] + "…" + k[-4:]


def is_local(cfg):
    """True si le cerveau tourne sur la machine (LM Studio, flm/NPU, Ollama)."""
    prov = (cfg.get("llm_provider") or "").lower()
    base = (cfg.get("llm_base_url") or "").lower()
    if prov in LOCAL_PROVIDERS:
        return True
    return any(h in base for h in ("127.0.0.1", "localhost", "[::1]", "0.0.0.0"))


def needs_key(cfg):
    """True si le fournisseur courant exige une clé et qu'aucune n'est disponible."""
    prov = cfg.get("llm_provider", "deepseek")
    if prov in LOCAL_PROVIDERS or is_local(cfg):
        return False          # un modèle local (NPU Ryzen AI, LM Studio) n'a pas de clé
    return not current_key(prov, cfg)
