"""'Find similar' must say so when its engine fails to load.

On Windows, torch failed to load with an OSError (WinError 1114, see
src/utils/msvc_runtime.py). The handler caught it with a bare print, and the
packaged app has no console — so clicking the button did nothing at all.

Same construction as test_main_window_pull.py: skip MainWindow's heavy
__init__ and set only the attributes the handler reads.
"""

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QMainWindow

import src.ui.main_window as mw
from src.ui.main_window import MainWindow


@pytest.fixture
def window(qapp):
    w = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(w)
    w.current_project = SimpleNamespace(images=[object()])
    w.similarity_service = None
    yield w
    w.deleteLater()


@pytest.fixture
def shown_errors(monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical",
                        lambda _parent, title, text: errors.append((title, text)))
    return errors


def _failing_service(exc):
    def factory():
        raise exc
    return factory


def test_dll_load_failure_shows_an_error(window, shown_errors, monkeypatch):
    monkeypatch.setattr(mw, "ImageSimilarityService", _failing_service(
        OSError("[WinError 1114] A dynamic link library (DLL) initialization "
                "routine failed")))

    window.on_find_similar_requested()

    assert len(shown_errors) == 1, "the failure was swallowed without a dialog"
    title, text = shown_errors[0]
    assert "WinError 1114" in text
    assert window.similarity_service is None


def test_missing_torch_still_gets_its_install_hint(window, shown_errors, monkeypatch):
    monkeypatch.setattr(mw, "ImageSimilarityService",
                        _failing_service(ImportError("No module named 'torch'")))

    window.on_find_similar_requested()

    assert len(shown_errors) == 1
    assert "pip install torch" in shown_errors[0][1]
