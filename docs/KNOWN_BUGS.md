# Known Bugs

Bugs surfaced by the test suite (`tests/`). Each entry has a reproduction, the
root cause, and a suggested fix. **These are intended to be fixed by a follow-up
agent.** When a bug is fixed, update or remove its guarding test (noted below).

Format for new entries: severity, location, guarding test, reproduction, root
cause, suggested fix.

---

**No open bugs.** BUG-1 (`crop_image` `subsampling='keep'` on JPEG sources),
BUG-2 (workspace discovery skipped when `projects.json` is absent), and BUG-3
(`_format_date` mangling `YYYY`) were fixed on 2026-07-14; their guarding tests
now assert the corrected behavior:

- `tests/test_crop_service.py::TestCropImageManualBox::test_jpeg_source_crop`
- `tests/test_project_manager.py::TestDiscovery`
- `tests/test_date_stamp_service.py::TestFormatDate::test_yyyy`
