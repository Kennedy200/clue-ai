"""Plugin discovery: plugins/<kind>/<name>/manifest.json, auto-discovered at startup."""
import json

from clue.core.config import ROOT

KINDS = ["llm", "tts", "asset", "payment", "email", "storage", "publisher", "caption_style", "template", "niche_pack"]
REQUIRED = {"name", "kind", "version", "title"}


def discover() -> list[dict]:
    """Return manifests for every valid plugin; invalid ones are reported, never fatal."""
    out = []
    base = ROOT / "plugins"
    if not base.exists():
        return out
    for mf in sorted(base.glob("*/*/manifest.json")):
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            missing = REQUIRED - set(m)
            if missing:
                raise ValueError(f"missing {sorted(missing)}")
            if m["kind"] != mf.parent.parent.name or m["kind"] not in KINDS:
                raise ValueError("kind must match its folder and be a known kind")
            m.setdefault("config", [])
            m.setdefault("enabled_by_default", False)
            m["path"] = str(mf.parent.relative_to(ROOT)).replace("\\", "/")
            m["valid"] = True
        except Exception as e:  # noqa: BLE001
            m = {"name": mf.parent.name, "kind": mf.parent.parent.name, "valid": False, "error": str(e), "path": str(mf.parent)}
        out.append(m)
    return out
