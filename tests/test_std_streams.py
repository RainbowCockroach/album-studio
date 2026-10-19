"""A windowed build has no console: sys.stdout/sys.stderr are None.

torch's first model download writes a progress bar to stderr, so "Find
similar" failed with "'NoneType' object has no attribute 'write'" — only in
the packaged app, never from source or under pytest.
"""

import sys

from src.main import ensure_std_streams


def test_missing_streams_become_writable(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_std_streams()
    sys.stderr.write("Downloading resnet50 ... 42%\r")
    print("diagnostic line")


def test_real_streams_are_left_alone(monkeypatch):
    out, err = object(), object()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    ensure_std_streams()
    assert sys.stdout is out and sys.stderr is err
