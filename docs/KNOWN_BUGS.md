# Known Bugs

Bugs surfaced by the test suite (`tests/`). Each entry has a reproduction, the
root cause, and a suggested fix. **These are intended to be fixed by a follow-up
agent.** When a bug is fixed, update or remove its guarding test (noted below).

---

## BUG-1 — `crop_image` fails on JPEG sources (`subsampling='keep'`)

**Severity:** High (silently breaks the core crop feature for JPEG inputs)
**Location:** `src/services/crop_service.py` → `CropService.crop_image` (save block, ~lines 174–185)
**Guarding test:** `tests/test_crop_service.py::TestCropImageManualBox::test_jpeg_source_crop_currently_fails` (marked `xfail(strict=True)`)

### Reproduction
```python
from PIL import Image
img = Image.new("RGB", (1000, 800)).save("s.jpg", "JPEG")
opened = Image.open("s.jpg")
resized = opened.crop((0, 0, 600, 400)).resize((1000, 666), Image.Resampling.LANCZOS)
resized.save("out.jpg", format="JPEG", quality=95, optimize=True, subsampling="keep")
# PIL raises: ValueError: Cannot use 'keep' when original image is not a JPEG
```

Inside `crop_image`, this exception is caught by the broad `except Exception`,
printed to stdout, and the method returns `False` — so the crop silently fails
and no output file is written.

### Root cause
`crop_image` records `original_format = img.format` **before** any processing,
then adds `save_params['subsampling'] = 'keep'` when the source was JPEG:

```python
if original_format == 'JPEG':
    save_params['subsampling'] = 'keep'
final_img.save(output_path, **save_params)
```

But `final_img` is a **new** image produced by `crop()` + `resize()`. It no
longer carries the source JPEG's quantization tables, so Pillow rejects
`subsampling='keep'`. `'keep'` is only valid when saving an image object that
still holds its original JPEG data — which a resized copy never does.

### Why it hasn't been noticed
The system is a phone-photo workflow; real inputs are **HEIC** (iPhone). For
HEIC/PNG sources `original_format != 'JPEG'`, the `'keep'` param is never added,
and cropping works. Only JPEG-sourced crops hit this path.

### Suggested fix
Drop `subsampling='keep'` for resized output — it cannot preserve anything
useful once the image has been resampled. Either remove the block entirely, or
replace `'keep'` with an explicit value (e.g. `subsampling=0` for 4:4:4, or just
rely on the `quality=95` default). Simplest:

```python
save_params = {'format': 'JPEG', 'quality': 95, 'optimize': True}
final_img.save(output_path, **save_params)
```

After fixing, flip `test_jpeg_source_crop_currently_fails` from `xfail` to a
normal passing assertion (it already asserts `ok is True`, so removing the
`@pytest.mark.xfail` decorator is enough — `strict=True` will otherwise report
an unexpected `XPASS`).

---

## BUG-2 — Workspace auto-discovery skipped on first load (no `projects.json`)

**Severity:** Medium (first-run projects not auto-registered)
**Location:** `src/services/project_manager.py` → `ProjectManager.load_projects` (early return, ~lines 40–41)
**Guarding tests:** `tests/test_project_manager.py::TestDiscovery` (seed `projects.json` via `save_projects()` before loading to work around this)

### Reproduction
```python
pm = ProjectManager(workspace_directory=ws)   # ws contains "2026-07/input/"
pm.load_projects()
assert "2026-07" in pm.get_project_names()     # FAILS — nothing discovered
```

### Root cause
`load_projects` returns **before** calling `_discover_workspace_projects` when
`projects.json` does not yet exist:

```python
def load_projects(self):
    self.projects.clear()
    if not os.path.exists(self.projects_file):
        return self.projects          # <-- early return skips discovery
    ...
    self._discover_workspace_projects()
    return self.projects
```

So a folder dropped into a **brand-new** workspace (no `projects.json` written
yet) is not auto-registered until some other action creates `projects.json`.

### Suggested fix
Run discovery even when `projects.json` is absent. Move the discovery call so it
executes on both branches, e.g.:

```python
def load_projects(self):
    self.projects.clear()
    if os.path.exists(self.projects_file):
        try:
            with open(self.projects_file, 'r') as f:
                data = json.load(f)
                for project_data in data.get("projects", []):
                    self.projects.append(Project.from_dict(project_data))
        except json.JSONDecodeError as e:
            print(f"Error loading projects.json: {e}")
        except Exception as e:
            print(f"Error loading projects: {e}")

    self._discover_workspace_projects()   # always run
    return self.projects
```

After fixing, the `TestDiscovery` tests no longer need the `pm.save_projects()`
seed line — remove those and the accompanying NOTE comment.

---

## BUG-3 — `_format_date` mangles any 4-digit-year token

**Severity:** Low (latent; not reachable via the current UI presets)
**Location:** `src/services/date_stamp_service.py` → `DateStampService._format_date` (~lines 195–201)
**Guarding test:** none yet (see note below)

### Root cause
`_format_date` does naive substring replacement, `YY` first:

```python
result = format_str
result = result.replace("YY", date.strftime("%y"))   # 2-digit year
result = result.replace("MM", date.strftime("%m"))
result = result.replace("DD", date.strftime("%d"))
```

A format containing a 4-digit-year token `YYYY` becomes `<yy><yy>` — e.g. for
2023, `"YYYY.MM.DD"` → `"2323.12.25"` — because the two `YY` pairs are each
replaced with the 2-digit year. There is no `YYYY` token support.

### Why it's low severity
The date-stamp format presets exposed in the UI are all 2-digit-year
(`YY.MM.DD`, `MM.DD.'YY`, `DD.MM.'YY`), matching the vintage-camera look. The
bug only manifests if a 4-digit-year format string is introduced.

### Suggested fix
Replace the longer token first, or use unambiguous tokens:

```python
result = format_str
result = result.replace("YYYY", date.strftime("%Y"))  # 4-digit first
result = result.replace("YY", date.strftime("%y"))
result = result.replace("MM", date.strftime("%m"))
result = result.replace("DD", date.strftime("%d"))
```

After fixing, add a `test_yyyy` case to
`tests/test_date_stamp_service.py::TestFormatDate`.
