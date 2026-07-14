"""Tests for src/services/server_sync_service.py.

Network access is faked by patching ``ServerSyncService._request`` to return an
in-memory response, so nothing here touches a socket. The SHA-256 verification
and ledger logic — the parts that guard the system-wide hash-identity invariant
— get the most coverage.
"""

import hashlib
import io
import json
from datetime import datetime, timezone

import pytest

from src.services.server_sync_service import (
    RemotePhoto,
    ServerSyncError,
    ServerSyncService,
    _parse_iso,
)


class FakeResponse:
    """Minimal stand-in for an http.client.HTTPResponse used as a context mgr."""

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    def read(self, n=-1):
        if n is None or n < 0:
            return self._buf.read()
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_service(tmp_path, base_url="https://srv.example", token="tok"):
    return ServerSyncService(base_url, token, str(tmp_path / "pulled_photos.json"))


def photo_dict(data: bytes, **overrides):
    """Build a /photos entry whose hash matches ``data``."""
    entry = {
        "hash": hashlib.sha256(data).hexdigest(),
        "originalName": "IMG_0001.jpg",
        "ext": "jpg",
        "size": len(data),
        "uploadedAt": "2026-06-15T10:00:00Z",
        "capturedAt": "2026-06-15T09:30:00Z",
    }
    entry.update(overrides)
    return entry


# ------------------------------------------------------------- timestamp parse

class TestParseIso:
    def test_trailing_z_is_utc_aware(self):
        # a trailing 'Z' is rewritten to +00:00 → tz-aware UTC
        assert _parse_iso("2026-06-15T09:30:00Z") == datetime(
            2026, 6, 15, 9, 30, 0, tzinfo=timezone.utc)

    def test_plain_offset(self):
        dt = _parse_iso("2026-06-15T09:30:00+00:00")
        assert dt is not None and dt.year == 2026

    def test_date_only_fallback(self):
        assert _parse_iso("2026-06-15") == datetime(2026, 6, 15)

    def test_leading_date_of_garbage_timestamp(self):
        # unparseable time portion → falls back to the leading YYYY-MM-DD
        assert _parse_iso("2026-06-15 not-a-time") == datetime(2026, 6, 15)

    @pytest.mark.parametrize("value", [None, "", "   ", "garbage", 12345])
    def test_returns_none_on_bad_input(self, value):
        assert _parse_iso(value) is None


# -------------------------------------------------------------- RemotePhoto

class TestRemotePhoto:
    def test_from_json_full(self):
        p = RemotePhoto.from_json(photo_dict(b"x"))
        assert p.original_name == "IMG_0001.jpg"
        assert p.ext == "jpg"
        assert p.captured_at == datetime(2026, 6, 15, 9, 30, 0, tzinfo=timezone.utc)

    def test_target_month_prefers_captured_at(self):
        p = RemotePhoto.from_json(photo_dict(
            b"x", capturedAt="2026-03-02T00:00:00Z", uploadedAt="2026-06-15T00:00:00Z"))
        assert p.target_month == "2026-03"

    def test_target_month_falls_back_to_uploaded_at(self):
        p = RemotePhoto.from_json(photo_dict(
            b"x", capturedAt=None, uploadedAt="2026-06-15T00:00:00Z"))
        assert p.target_month == "2026-06"

    def test_missing_uploaded_at_falls_back_to_epoch(self):
        p = RemotePhoto.from_json({"hash": "abc"})
        assert p.uploaded_at == datetime.fromtimestamp(0)
        assert p.captured_at is None

    def test_group_by_month(self):
        photos = [
            RemotePhoto.from_json(photo_dict(b"a", capturedAt="2026-03-01T00:00:00Z")),
            RemotePhoto.from_json(photo_dict(b"b", capturedAt="2026-03-20T00:00:00Z")),
            RemotePhoto.from_json(photo_dict(b"c", capturedAt="2026-04-01T00:00:00Z")),
        ]
        groups = ServerSyncService.group_by_month(photos)
        assert set(groups) == {"2026-03", "2026-04"}
        assert len(groups["2026-03"]) == 2


# ------------------------------------------------------------------- listing

class TestListRemote:
    def test_list_remote_filters_photos_without_hash(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        body = json.dumps({"photos": [
            photo_dict(b"a"),
            {"originalName": "no_hash.jpg"},  # dropped — empty hash
        ]}).encode()
        monkeypatch.setattr(svc, "_request", lambda path, timeout: FakeResponse(body))
        photos = svc.list_remote(None)
        assert len(photos) == 1

    def test_list_remote_invalid_json_raises(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        monkeypatch.setattr(svc, "_request", lambda path, timeout: FakeResponse(b"nope"))
        with pytest.raises(ServerSyncError):
            svc.list_remote(None)


# -------------------------------------------------------------------- ledger

class TestLedger:
    def test_is_pulled_false_on_empty(self, tmp_path):
        svc = make_service(tmp_path)
        assert svc.is_pulled("deadbeef") is False

    def test_meta_key_is_not_a_pulled_hash(self, tmp_path):
        svc = make_service(tmp_path)
        svc.set_last_pull_month("2026-06")
        assert svc.is_pulled("_meta") is False

    def test_last_pull_month_round_trip_persists(self, tmp_path):
        svc = make_service(tmp_path)
        assert svc.last_pull_month is None
        svc.set_last_pull_month("2026-06")
        assert svc.last_pull_month == "2026-06"
        # a fresh instance reads the same on-disk ledger
        assert make_service(tmp_path).last_pull_month == "2026-06"

    def test_corrupt_ledger_treated_as_empty(self, tmp_path):
        ledger = tmp_path / "pulled_photos.json"
        ledger.write_text("{ corrupt")
        svc = make_service(tmp_path)
        assert svc.is_pulled("x") is False
        assert svc.last_pull_month is None


class TestGetNewPhotos:
    def test_excludes_already_pulled(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        seen, fresh = photo_dict(b"seen"), photo_dict(b"fresh")
        body = json.dumps({"photos": [seen, fresh]}).encode()
        monkeypatch.setattr(svc, "_request", lambda path, timeout: FakeResponse(body))
        # mark one as already pulled
        svc._record_pulled(seen["hash"], "2026-06", "seen.jpg")

        new = svc.get_new_photos(None)
        assert [p.hash for p in new] == [fresh["hash"]]

    def test_auto_uses_last_pull_month(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        svc.set_last_pull_month("2026-05")
        captured = {}

        def fake_request(path, timeout):
            captured["path"] = path
            return FakeResponse(json.dumps({"photos": []}).encode())

        monkeypatch.setattr(svc, "_request", fake_request)
        svc.get_new_photos_auto()
        assert "since=2026-05" in captured["path"]


# ------------------------------------------------------------- filename logic

class TestFilenames:
    def test_safe_filename_sanitizes(self, tmp_path):
        svc = make_service(tmp_path)
        p = RemotePhoto.from_json(photo_dict(b"x", originalName="a/b:c*.jpg"))
        name = svc._safe_filename(p)
        # path components stripped, unsafe chars replaced
        assert "/" not in name and ":" not in name and "*" not in name
        assert name.endswith(".jpg")

    def test_safe_filename_falls_back_to_hash(self, tmp_path):
        svc = make_service(tmp_path)
        p = RemotePhoto.from_json(photo_dict(b"x", originalName="", ext="png"))
        assert svc._safe_filename(p) == f"{p.hash}.png"

    def test_unique_path_avoids_collision(self, tmp_path):
        svc = make_service(tmp_path)
        (tmp_path / "IMG.jpg").write_text("existing")
        result = svc._unique_path(tmp_path, "IMG.jpg")
        assert result.name == "IMG_2.jpg"


# ------------------------------------------------------------------ download

class TestDownload:
    def _patch_bytes(self, svc, monkeypatch, data: bytes):
        monkeypatch.setattr(
            svc, "_request", lambda path, timeout: FakeResponse(data))

    def test_download_verifies_hash_and_ledgers(self, tmp_path, monkeypatch):
        data = b"the real photo bytes"
        svc = make_service(tmp_path)
        self._patch_bytes(svc, monkeypatch, data)
        photo = RemotePhoto.from_json(photo_dict(data, originalName="pic.jpg"))

        dest = tmp_path / "2026-06" / "input"
        result = svc.download(photo, dest, "2026-06")

        assert result.exists()
        assert result.read_bytes() == data
        assert result.name == "pic.jpg"
        # recorded in the ledger so a re-pull skips it
        assert svc.is_pulled(photo.hash) is True

    def test_download_hash_mismatch_rejects_and_does_not_ledger(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        # server returns different bytes than the advertised hash
        self._patch_bytes(svc, monkeypatch, b"tampered bytes")
        photo = RemotePhoto.from_json(photo_dict(b"original bytes"))

        dest = tmp_path / "2026-06" / "input"
        with pytest.raises(ServerSyncError, match="[Hh]ash mismatch"):
            svc.download(photo, dest, "2026-06")

        assert svc.is_pulled(photo.hash) is False
        # no leftover file remains in the destination
        assert list(dest.iterdir()) == []

    def test_download_no_collision_second_file_suffixed(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        dest = tmp_path / "2026-06" / "input"

        a, b = b"first photo", b"second photo"
        pa = RemotePhoto.from_json(photo_dict(a, originalName="same.jpg"))
        pb = RemotePhoto.from_json(photo_dict(b, originalName="same.jpg"))

        self._patch_bytes(svc, monkeypatch, a)
        r1 = svc.download(pa, dest, "2026-06")
        self._patch_bytes(svc, monkeypatch, b)
        r2 = svc.download(pb, dest, "2026-06")

        assert r1.name == "same.jpg"
        assert r2.name == "same_2.jpg"


# ------------------------------------------------------------- test_connection

class TestConnection:
    def test_no_url_configured(self, tmp_path):
        svc = ServerSyncService("", "tok", str(tmp_path / "l.json"))
        ok, msg = svc.test_connection()
        assert ok is False
        assert "URL" in msg

    def test_health_ok_and_token_accepted(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)

        def fake_request(path, timeout, auth=True):
            if path == "/health":
                return FakeResponse(json.dumps({"status": "ok"}).encode())
            return FakeResponse(json.dumps({"photos": []}).encode())

        monkeypatch.setattr(svc, "_request", fake_request)
        ok, msg = svc.test_connection()
        assert ok is True
        assert "OK" in msg

    def test_health_not_ok(self, tmp_path, monkeypatch):
        svc = make_service(tmp_path)
        monkeypatch.setattr(
            svc, "_request",
            lambda path, timeout, auth=True: FakeResponse(json.dumps({"status": "down"}).encode()))
        ok, _ = svc.test_connection()
        assert ok is False
