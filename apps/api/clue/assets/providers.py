"""Keyless visual sources. Priority: user uploads > procedural (FFmpeg) > Pollinations AI images > Wikimedia Commons.

No stock-video API key is ever required. Every downloaded asset records provider, author and licence.
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from clue.core import storage

UA = {"User-Agent": "ClueAI/0.3 (open-source short video maker; https://github.com/Kennedy200/clue-ai)"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class AssetError(Exception):
    pass


@dataclass
class AssetResult:
    provider: str
    url: str
    title: str
    author: str = ""
    license: str = ""
    page_url: str = ""

    @property
    def attribution(self) -> str:
        bits = [self.title, f"by {self.author}" if self.author else "", self.license, self.page_url]
        return " · ".join(b for b in bits if b)


class AssetProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[AssetResult]: ...


BLOCKED_LICENSE = re.compile(r"(?<![A-Za-z])(NC|ND)(?![A-Za-z])|non-?commercial|no[- ]?deriv", re.I)


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


class WikimediaProvider(AssetProvider):
    """Freely licensed photos from Wikimedia Commons (public API, no key)."""
    name = "wikimedia"
    API = "https://commons.wikimedia.org/w/api.php"

    def search(self, query: str, limit: int = 5) -> list[AssetResult]:
        params = {
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": limit * 3,
            "gsrsearch": f"filetype:bitmap {query[:80]}", "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1350,
        }
        try:
            r = httpx.get(self.API, params=params, headers=UA, timeout=20)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise AssetError(f"Wikimedia is unreachable ({e.__class__.__name__}).") from e
        pages = (r.json().get("query") or {}).get("pages", {})
        out = []
        for p in sorted(pages.values(), key=lambda x: x.get("index", 0)):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = _strip_html(meta.get("LicenseShortName", {}).get("value", ""))
            if not info.get("thumburl") or info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if not lic or BLOCKED_LICENSE.search(lic):
                continue  # unknown, non-commercial (NC) and no-derivatives (ND) licences are skipped
            out.append(AssetResult("wikimedia", info["thumburl"], _strip_html(p.get("title", "")).removeprefix("File:"),
                                   _strip_html(meta.get("Artist", {}).get("value", "")), lic, info.get("descriptionurl", "")))
            if len(out) >= limit:
                break
        return out


class PollinationsProvider(AssetProvider):
    """Keyless AI images. The anonymous tier is slow and rate-limited, so this is best-effort and always cached."""
    name = "pollinations"

    def search(self, query: str, limit: int = 1) -> list[AssetResult]:
        prompt = quote(query[:300])
        seed = int(hashlib.sha256(query.encode()).hexdigest()[:6], 16)
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true&seed={seed}"
        return [AssetResult("pollinations", url, query[:80], "AI generated (Pollinations)", "AI-generated", "https://pollinations.ai")]


PROVIDERS: dict[str, AssetProvider] = {"wikimedia": WikimediaProvider(), "pollinations": PollinationsProvider()}


def fetch(result: AssetResult, user_id: str, timeout: float = 90) -> str:
    """Download (or reuse) the image. Returns a storage-relative path. Cached by URL hash."""
    h = hashlib.sha256(result.url.encode()).hexdigest()[:24]
    d = storage.root() / "cache" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    for existing in d.glob(f"{h}.*"):
        return f"cache/assets/{existing.name}"
    try:
        with httpx.stream("GET", result.url, headers=UA, timeout=timeout, follow_redirects=True) as r:
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            ext = {"image/jpeg": "jpg", "image/png": "png"}.get(ctype.split(";")[0])
            if not ext:
                raise AssetError(f"Unexpected file type '{ctype}'.")
            data = bytearray()
            for chunk in r.iter_bytes(1 << 16):
                data += chunk
                if len(data) > MAX_IMAGE_BYTES:
                    raise AssetError("Image is too large.")
    except httpx.HTTPError as e:
        raise AssetError(f"Could not download the image ({e.__class__.__name__}).") from e
    (d / f"{h}.{ext}").write_bytes(bytes(data))
    return f"cache/assets/{h}.{ext}"
