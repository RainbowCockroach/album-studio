"""The headless --self-test must report failures, not just successes.

Its whole job is to say *why* the packaged app's "Find similar" fails on some
machine nobody is sitting at, so a failure that leaves no report — or a report
that says PASS — would defeat it. The real engine is swapped for a stub here;
the packaged app runs it for real (see src/self_test.py).
"""

import numpy as np
import pytest

from src.self_test import run_self_test


class StubService:
    def __init__(self, vectors):
        self.vectors = vectors

    def load_images_from_directory(self, directory, formats):
        return [{"path": f"{directory}/{name}", "features": vec}
                for name, vec in self.vectors.items()]

    def find_similar_images(self, target, candidates, top_k, min_similarity):
        return [(c, 0.9) for c in candidates][:top_k]


@pytest.fixture
def report(tmp_path):
    return tmp_path / "report.txt"


def test_working_engine_passes(report, tmp_path):
    svc = StubService({"a.jpg": np.ones(4), "b.jpg": np.ones(4)})
    assert run_self_test(str(report), str(tmp_path), lambda: svc) == 0
    text = report.read_text()
    assert "b.jpg" in text and text.rstrip().endswith("PASS")


def test_engine_that_cannot_load_fails_with_the_reason(report, tmp_path):
    def broken():
        raise OSError("[WinError 1114] A dynamic link library (DLL) "
                      "initialization routine failed")

    assert run_self_test(str(report), str(tmp_path), broken) == 1
    text = report.read_text()
    assert "FAIL load similarity engine" in text and "WinError 1114" in text
    assert "PASS" not in text


def test_photos_without_features_fail(report, tmp_path):
    svc = StubService({"a.jpg": None, "b.jpg": None})
    assert run_self_test(str(report), str(tmp_path), lambda: svc) == 1
    assert "FAIL need at least 2 photos" in report.read_text()


def test_no_matches_fail(report, tmp_path):
    svc = StubService({"a.jpg": np.ones(4), "b.jpg": np.ones(4)})
    svc.find_similar_images = lambda *a, **k: []
    assert run_self_test(str(report), str(tmp_path), lambda: svc) == 1
    assert "FAIL no matches" in report.read_text()
