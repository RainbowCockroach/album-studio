"""Regression tests for the 'Pull from Server' dialog handlers.

This is the one place the suite reaches into ``src/ui``. Widgets are otherwise
untested by design, but the pull handlers hid a bug that no service-level test
could ever catch: ``QProgressDialog.close()`` emits ``canceled()``, so closing
the busy dialog *before* reading the cancel flag made every pull look like a
user cancellation. The service layer was healthy the whole time — clicking the
button simply did nothing, silently, including on connection errors.

``MainWindow.__init__`` reads the real user config, scans the workspace and
kicks off a network update check, so these tests bypass it: they allocate the
instance and run only ``QMainWindow.__init__`` to get a valid Qt object, then
wire the pull dialog exactly as ``on_pull_from_server_requested`` does. Nothing
here touches a socket.
"""

from datetime import datetime, timezone

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QProgressDialog

from src.services.server_sync_service import (
    RemotePhoto, ServerSyncError, ServerSyncService)
from src.ui.main_window import MainWindow, PullDownloadWorker
from src.ui.widgets.toolbar_top import PULL_BTN_IDLE_TEXT, ProjectToolbar


@pytest.fixture
def window(qapp):
    """A MainWindow with a live Qt object but none of its heavy __init__.

    A real ProjectToolbar is attached because the pull handlers drive the pull
    button's busy/idle state through it; a stub would let a wrong call pass.
    """
    w = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(w)
    w.project_toolbar = ProjectToolbar()
    yield w
    w.deleteLater()


def wire_pull_dialog(window):
    """Set up the listing dialog exactly as on_pull_from_server_requested does."""
    window._pull_list_dialog = QProgressDialog(
        "Checking server for new photos…", "Cancel", 0, 0, window)
    window._pull_list_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    window._pull_list_dialog.setMinimumDuration(0)
    window._pull_list_cancelled = False
    window._pull_list_dialog.canceled.connect(window._on_pull_list_cancelled)


def make_photo(hash_, name, captured, size=1000):
    when = datetime(2026, 7, 5, 19, 2, 10, tzinfo=timezone.utc)
    return RemotePhoto(hash=hash_, original_name=name, ext="jpg", size=size,
                       uploaded_at=when, captured_at=captured)


def test_qprogressdialog_close_emits_canceled(qapp):
    """Pin the Qt behaviour the bug was built on; if this ever changes, know it."""
    dialog = QProgressDialog("Checking…", "Cancel", 0, 0, None)
    dialog.setMinimumDuration(0)
    fired = []
    dialog.canceled.connect(lambda: fired.append(1))

    dialog.close()

    assert fired, "QProgressDialog.close() no longer self-emits canceled()"


def test_closing_list_dialog_is_not_a_cancel(window):
    """The regression: closing the dialog must not report a user cancellation."""
    wire_pull_dialog(window)

    assert window._close_pull_list_dialog() is False


def click_cancel(dialog):
    """Simulate the user hitting Cancel.

    Note ``QProgressDialog.cancel()`` is *not* the equivalent: it flips
    ``wasCanceled()`` without emitting ``canceled()``. Qt wires the real button
    up as ``clicked -> canceled``, so emitting the signal is what a click does.
    """
    dialog.canceled.emit()


def test_real_cancel_is_still_reported(window):
    """Guards the opposite failure: a genuine cancel must survive the close."""
    wire_pull_dialog(window)

    click_cancel(window._pull_list_dialog)

    assert window._close_pull_list_dialog() is True


def test_pull_error_reaches_the_user(window, monkeypatch):
    """A listing failure must surface, not vanish. This was silent before."""
    wire_pull_dialog(window)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        lambda *a, **k: shown.append((a[1], a[2])))

    window._on_pull_error("Connection refused")

    assert shown == [("Pull Failed", "Connection refused")]


def test_pull_error_stays_quiet_when_cancelled(window, monkeypatch):
    """A user who cancelled should not then get an error popup."""
    wire_pull_dialog(window)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        lambda *a, **k: shown.append((a[1], a[2])))

    click_cancel(window._pull_list_dialog)
    window._on_pull_error("Connection refused")

    assert shown == []


def test_pull_list_shows_breakdown(window, monkeypatch, tmp_path):
    """The reported symptom: a successful listing must offer the download."""
    wire_pull_dialog(window)
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: (asked.append(a[2]), QMessageBox.StandardButton.No)[1])

    service = ServerSyncService("https://example.invalid", "tok",
                                str(tmp_path / "ledger.json"))
    photos = [
        make_photo("a" * 12, "june.jpg", datetime(2026, 6, 29, tzinfo=timezone.utc)),
        make_photo("b" * 12, "july.jpg", datetime(2026, 7, 5, tzinfo=timezone.utc)),
    ]

    window._on_pull_list_ready(service, str(tmp_path), photos)

    assert len(asked) == 1, "the download confirmation never appeared"
    assert "2 new photos" in asked[0]
    assert "2026-06 → 1" in asked[0] and "2026-07 → 1" in asked[0]


def test_pull_list_reports_empty_server(window, monkeypatch, tmp_path):
    """An empty listing must say so rather than look like a dead button."""
    wire_pull_dialog(window)
    shown = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: shown.append((a[1], a[2])))

    service = ServerSyncService("https://example.invalid", "tok",
                                str(tmp_path / "ledger.json"))
    window._on_pull_list_ready(service, str(tmp_path), [])

    assert shown == [("Up to Date", "No new photos on the server.")]


# ------------------------------------------------------- pull button feedback

def test_pull_button_shows_busy_while_checking(qapp):
    """The toolbar itself must show the pull is alive, not just the dialog."""
    toolbar = ProjectToolbar()

    toolbar.set_pull_checking()

    assert toolbar.pull_server_btn.text() == "Checking…"
    assert toolbar.pull_server_btn.isEnabled() is False, \
        "a busy button must not accept a second pull"


def test_pull_button_counts_files_while_downloading(qapp):
    toolbar = ProjectToolbar()

    toolbar.set_pull_progress(3, 40)

    assert toolbar.pull_server_btn.text() == "Pulling 3/40"


def test_pull_button_returns_to_idle(qapp):
    toolbar = ProjectToolbar()
    toolbar.set_pull_checking()

    toolbar.reset_pull_button()

    assert toolbar.pull_server_btn.text() == PULL_BTN_IDLE_TEXT
    assert toolbar.pull_server_btn.isEnabled() is True


def test_button_is_released_when_listing_fails(window, monkeypatch):
    """A dead-end error must not leave the button stuck disabled forever."""
    wire_pull_dialog(window)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    window.project_toolbar.set_pull_checking()

    window._on_pull_error("Connection refused")

    assert window.project_toolbar.pull_server_btn.isEnabled() is True


def test_button_is_released_when_server_is_up_to_date(window, monkeypatch, tmp_path):
    wire_pull_dialog(window)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    window.project_toolbar.set_pull_checking()

    service = ServerSyncService("https://example.invalid", "tok",
                                str(tmp_path / "ledger.json"))
    window._on_pull_list_ready(service, str(tmp_path), [])

    assert window.project_toolbar.pull_server_btn.isEnabled() is True


def test_button_is_released_when_user_declines_download(window, monkeypatch, tmp_path):
    """Answering No to the confirmation must hand the button back."""
    wire_pull_dialog(window)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    window.project_toolbar.set_pull_checking()

    service = ServerSyncService("https://example.invalid", "tok",
                                str(tmp_path / "ledger.json"))
    photos = [make_photo("a" * 12, "june.jpg",
                         datetime(2026, 6, 29, tzinfo=timezone.utc))]
    window._on_pull_list_ready(service, str(tmp_path), photos)

    assert window.project_toolbar.pull_server_btn.isEnabled() is True


# ------------------------------------------------- download progress reporting

class FakeService:
    """A ServerSyncService stand-in that replays byte progress per photo.

    ``chunks_by_hash`` maps a photo hash to the running byte counts its
    download should report; a hash mapped to an exception raises it instead.
    """

    def __init__(self, chunks_by_hash):
        self.chunks_by_hash = chunks_by_hash
        self.last_pull_month = None

    def download(self, photo, dest_dir, project, progress_callback=None):
        outcome = self.chunks_by_hash[photo.hash]
        if isinstance(outcome, Exception):
            raise outcome
        for done in outcome:
            if progress_callback:
                progress_callback(done, photo.size)

    def set_last_pull_month(self, month):
        self.last_pull_month = month

    # Delegated so the fake groups photos exactly as the real service does.
    group_by_month = staticmethod(ServerSyncService.group_by_month)


def run_worker(service, photos, monkeypatch, tmp_path):
    """Run a PullDownloadWorker synchronously, returning its progress emits.

    ``run()`` is called directly rather than via ``start()``: the aggregation
    under test is plain logic, and a real thread would only add flakiness.
    The emit throttle is disabled so every callback is observable.
    """
    monkeypatch.setattr(PullDownloadWorker, "_EMIT_INTERVAL", 0)
    jobs = [(p, str(tmp_path / "input"), "2026-07") for p in photos]
    worker = PullDownloadWorker(service, jobs, "2026-07")
    seen = []
    worker.progress_updated.connect(seen.append)
    worker.run()
    return seen


def test_progress_accumulates_across_files(qapp, monkeypatch, tmp_path):
    """bytes_done must count earlier files, not restart at each one."""
    a = make_photo("a" * 12, "a.jpg", None, size=100)
    b = make_photo("b" * 12, "b.jpg", None, size=100)
    service = FakeService({a.hash: [50, 100], b.hash: [50, 100]})

    seen = run_worker(service, [a, b], monkeypatch, tmp_path)

    assert [e["bytes_total"] for e in seen] == [200] * len(seen)
    # Per file: a forced emit on start, one per chunk, a forced emit on
    # completion. The second file's counts are offset by the first file's 100.
    assert [e["bytes_done"] for e in seen] == [0, 50, 100, 100,
                                               100, 150, 200, 200]
    assert [e["bytes_done"] for e in seen] == sorted(e["bytes_done"] for e in seen), \
        "the bar must never jump backwards"


def test_progress_clamps_when_server_under_reports_size(qapp, monkeypatch, tmp_path):
    """Real bytes exceeding the advertised size must not overrun the bar."""
    a = make_photo("a" * 12, "a.jpg", None, size=100)
    # server said 100 bytes; the stream actually delivers 250
    service = FakeService({a.hash: [100, 250]})

    seen = run_worker(service, [a], monkeypatch, tmp_path)

    assert max(e["bytes_done"] for e in seen) == 100, "bar overran its maximum"


def test_failed_file_still_advances_the_bar(qapp, monkeypatch, tmp_path):
    """A mid-pull failure must not strand the bar short of 100%."""
    a = make_photo("a" * 12, "a.jpg", None, size=100)
    b = make_photo("b" * 12, "b.jpg", None, size=100)
    service = FakeService({a.hash: ServerSyncError("hash mismatch"),
                           b.hash: [100]})

    seen = run_worker(service, [a, b], monkeypatch, tmp_path)

    assert seen[-1]["bytes_done"] == 200
    assert seen[-1]["bytes_total"] == 200


def test_progress_labels_each_file(qapp, monkeypatch, tmp_path):
    """The dialog reads index/count/filename straight off these emits."""
    a = make_photo("a" * 12, "first.jpg", None, size=10)
    b = make_photo("b" * 12, "second.jpg", None, size=10)
    service = FakeService({a.hash: [10], b.hash: [10]})

    seen = run_worker(service, [a, b], monkeypatch, tmp_path)

    assert (seen[0]["index"], seen[0]["filename"]) == (0, "first.jpg")
    assert seen[-1]["index"] == 1 and seen[-1]["filename"] == "second.jpg"
    assert all(e["count"] == 2 for e in seen)


def test_bar_reaches_full_even_when_throttled(qapp, monkeypatch, tmp_path):
    """The last chunk of each file must survive the emit throttle.

    With the throttle left at its real value, a fast download's chunk
    callbacks are all coalesced away; only the forced per-file emits get
    through. The final one has to land on 100% or the dialog closes on a
    part-filled bar.
    """
    a = make_photo("a" * 12, "a.jpg", None, size=100)
    b = make_photo("b" * 12, "b.jpg", None, size=100)
    service = FakeService({a.hash: [50, 100], b.hash: [50, 100]})

    jobs = [(p, str(tmp_path / "input"), "2026-07") for p in (a, b)]
    worker = PullDownloadWorker(service, jobs, "2026-07")  # real throttle
    seen = []
    worker.progress_updated.connect(seen.append)
    worker.run()

    assert seen[-1]["bytes_done"] == seen[-1]["bytes_total"] == 200, \
        "the bar never reached 100%"


def test_empty_pull_does_not_divide_by_zero(qapp, monkeypatch, tmp_path):
    """No jobs means no emits — and no ZeroDivisionError building the totals."""
    assert run_worker(FakeService({}), [], monkeypatch, tmp_path) == []


def test_button_survives_finish_landing_inside_setvalue(window, qapp, monkeypatch,
                                                        tmp_path):
    """The pull button must be idle once the pull ends. Full flow, no sockets.

    Qt runs processEvents() inside a modal QProgressDialog.setValue(), so the
    worker's finished_signal can be delivered *during* a progress update, and
    on_finished then runs re-entrantly, half-way through on_progress. Anything
    on_progress writes after setValue() therefore lands after on_finished has
    already reset the button, stranding it disabled at "Pulling n/n" for the
    rest of the session.

    setValue() is patched to pump the event loop so that interleaving happens
    every run rather than only when the timing lines up.
    """
    real_set_value = QProgressDialog.setValue

    def pumping_set_value(self, value):
        real_set_value(self, value)
        qapp.processEvents()  # what a modal setValue() does on its own

    monkeypatch.setattr(QProgressDialog, "setValue", pumping_set_value)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(MainWindow, "_refresh_projects_after_pull", lambda self: None)

    wire_pull_dialog(window)
    photos = [make_photo(chr(97 + i) * 12, f"IMG_{i}.jpg", None, size=512 * 1024)
              for i in range(3)]
    service = FakeService({p.hash: [256 * 1024, 512 * 1024] for p in photos})

    window._on_pull_list_ready(service, str(tmp_path), photos)
    assert window._pull_download_worker.wait(10_000), "worker never finished"
    for _ in range(50):
        qapp.processEvents()

    button = window.project_toolbar.pull_server_btn
    assert (button.text(), button.isEnabled()) == (PULL_BTN_IDLE_TEXT, True), \
        "the pull button was left stranded after the pull finished"
