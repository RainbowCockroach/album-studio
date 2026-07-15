# Known Bugs

Bugs surfaced by the test suite (`tests/`). Each entry has a reproduction, the
root cause, and a suggested fix. **These are intended to be fixed by a follow-up
agent.** When a bug is fixed, update or remove its guarding test (noted below).

Format for new entries: severity, location, guarding test, reproduction, root
cause, suggested fix.

---

No open bugs.

---

**Fixed.** BUG-1 (`crop_image` `subsampling='keep'` on JPEG sources),
BUG-2 (workspace discovery skipped when `projects.json` is absent), and BUG-3
(`_format_date` mangling `YYYY`) were fixed on 2026-07-14; BUG-4 (a manual crop
box surviving a re-tag to a different aspect ratio) was fixed on 2026-07-15.

BUG-5 through BUG-8 were fixed on 2026-07-15. All four were packaging faults, and
they are worth remembering together, because the pattern is the point: each one
was invisible from source, silent in the build, and only observable in the
shipped `.app`. The DMG was doubly broken — the app inside it could not launch,
and the image had no `/Applications` symlink to drag it to.

- **BUG-5 — the packaged app crashed on launch.** PyInstaller was pointed at
  `src/main.py`, whose relative imports cannot work in a script executed as
  `__main__`. The app died instantly with `ImportError`, and PyInstaller's
  analysis could not follow those imports either, so it discovered **none of
  `src/`** — a 70 MB bundle that built with exit code 0 and was dead on arrival
  (a correct build is ~557 MB, mostly torch). The missing weight was the tell.
  Both builders now point at the `run.py` shim, which keeps `src` a real package.
- **BUG-6 — the app could not see its own bundled `config/`.** `get_config_dir()`
  and `get_assets_dir()` built paths from `dirname(sys.executable)`, which in a
  `.app` is `Contents/MacOS` — where PyInstaller 6 puts *only* the binary. Data
  lives in `Contents/Frameworks`, the real `sys._MEIPASS` (confirmed by probing a
  frozen build, not by reading docs). Nothing raised: `Config` fell back to
  defaults and the app started with **no size groups at all**. Both resolvers now
  go through `_bundled_resource_dir()`.
- **BUG-7 — `assets/` was never bundled.** Only `--add-data=config:config` was
  passed, so the DSEG7 font was absent and `DateStampService._get_font()` fell
  back to Pillow's default bitmap font. Date stamps still drew, just wrong.
- **BUG-8 — the window icon never loaded.** `QIcon("assets/app_icon.png")` is
  relative, so it resolved against the working directory — `/` under Finder — and
  `QIcon` reports nothing for a file it cannot find.

The through-line: every one degraded silently rather than failing. Three of the
four were masked by a `try`/`exists()` fallback that made a broken install look
like a working one, and the fourth by a build that exited 0. `build.py` now
*aborts* on a missing icon for exactly this reason — it used to drop the `--icon`
flag and ship PyInstaller's own Python logo.

Their guarding tests now assert the corrected behavior:

- `tests/test_crop_service.py::TestCropImageManualBox::test_jpeg_source_crop`
- `tests/test_project_manager.py::TestDiscovery`
- `tests/test_date_stamp_service.py::TestFormatDate::test_yyyy`
- `tests/test_models.py::TestSetTagsCropBox`
- `tests/test_build_entry_point.py` (BUG-5)
- `tests/test_frozen_resources.py` (BUG-6, BUG-8)
- `tests/test_build_packaging.py::TestBundledData` (BUG-7)
