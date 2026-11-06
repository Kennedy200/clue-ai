import httpx

from clue.assets import providers as pv


class R:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def test_wikimedia_keeps_license_and_skips_noncommercial(monkeypatch):
    def page(i, lic, mime="image/jpeg"):
        return {"index": i, "title": f"File:P{i}.jpg", "imageinfo": [{"thumburl": f"http://x/{i}.jpg", "mime": mime, "descriptionurl": f"http://x/p{i}",
                "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "<a href='x'>Ada</a>"}}}]}
    data = {"query": {"pages": {"1": page(1, "CC BY-SA 4.0"), "2": page(2, "CC BY-NC 4.0"), "3": page(3, ""), "4": page(4, "Public domain", "image/svg+xml"), "5": page(5, "Public domain")}}}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: R(data))
    res = pv.WikimediaProvider().search("lagos", 5)
    assert [r.title for r in res] == ["P1.jpg", "P5.jpg"]
    assert "by Ada" in res[0].attribution and "CC BY-SA 4.0" in res[0].attribution


def test_fetch_rejects_non_image_and_caches(monkeypatch, tmp_path):
    class S:
        def __init__(self, ctype, body):
            self.headers, self.body = {"content-type": ctype}, body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, n):
            yield self.body

    res = pv.AssetResult("t", "http://x/a.html", "t")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: S("text/html", b"<html>"))
    try:
        pv.fetch(res, "u")
        raise AssertionError("should reject")
    except pv.AssetError:
        pass
    ok = pv.AssetResult("t", "http://x/cached.jpg", "t")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: S("image/jpeg", b"\xff\xd8data"))
    p1 = pv.fetch(ok, "u")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used twice")))
    assert pv.fetch(ok, "u") == p1


def test_license_filter_catches_nc_and_nd_variants():
    for bad in ["CC BY-NC 4.0", "CC BY-NC-SA 3.0", "CC BY-ND 2.0", "CC BY-NC-ND 4.0", "Non-commercial use only"]:
        assert pv.BLOCKED_LICENSE.search(bad), bad
    for ok in ["CC BY-SA 4.0", "CC BY 2.0", "Public domain", "CC0", "GFDL"]:
        assert not pv.BLOCKED_LICENSE.search(ok), ok
