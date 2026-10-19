"""Headless self-test of "Find similar", runnable from the packaged app.

    AlbumStudio.exe --self-test <report.txt> <photo_dir>

Runs the same steps as the button, with no window: build the similarity
service (loads torch and downloads ResNet50 on first use), scan <photo_dir>
the way SimilaritySearchWorker scans the comparison folder, then rank matches
for its first photo. Writes a plain-text report and returns 0 only if every
step worked and at least one match came back.

It exists because the failures that matter here — DLLs that will not load,
modules PyInstaller left out, certificates a fresh Windows lacks — only appear
inside the packaged app on a particular machine. This lets a clean Windows
Sandbox verify a build with no one at the keyboard.
"""

import os
import platform
import sys
import time
import traceback
from typing import List

# Matches config/settings.json's default supported_formats.
PHOTO_EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic", ".heif"]


def run_self_test(report_path: str, photo_dir: str, service_factory=None) -> int:
    lines: List[str] = []

    def log(message: str) -> None:
        lines.append(message)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    log(f"Album Studio self-test  frozen={bool(getattr(sys, 'frozen', False))}")
    log(f"Python {platform.python_version()} on {platform.platform()}")
    log(f"SSL_CERT_FILE={os.environ.get('SSL_CERT_FILE')}")

    step = "start"
    try:
        step = "load similarity engine (torch, torchvision, model download)"
        started = time.perf_counter()
        if service_factory is None:
            from .services.image_similarity_service import ImageSimilarityService
            service_factory = ImageSimilarityService
        service = service_factory()
        log(f"OK   {step}  {time.perf_counter() - started:.1f}s")

        step = "scan photos and extract features"
        started = time.perf_counter()
        images = service.load_images_from_directory(photo_dir, PHOTO_EXTENSIONS)
        with_features = [i for i in images if i["features"] is not None]
        log(f"OK   {step}  {len(with_features)}/{len(images)} photos  "
            f"{time.perf_counter() - started:.1f}s")
        if len(with_features) < 2:
            log(f"FAIL need at least 2 photos with features in {photo_dir}")
            return 1

        step = "rank similar photos"
        from .models.image_item import ImageItem
        items = []
        for entry in with_features:
            item = ImageItem(entry["path"])
            item.feature_vector = entry["features"]
            items.append(item)
        target, candidates = items[0], items[1:]
        results = service.find_similar_images(target, candidates, top_k=5,
                                              min_similarity=0.0)
        log(f"OK   {step}  target={os.path.basename(target.file_path)}")
        for item, score in results:
            # find_similar_images is typed loosely (object); these are ImageItems.
            log(f"       {score:.3f}  {os.path.basename(getattr(item, 'file_path'))}")
        if not results:
            log("FAIL no matches returned")
            return 1
    except BaseException as e:  # noqa: BLE001 - the report must say why
        log(f"FAIL {step}: {type(e).__name__}: {e}")
        log(traceback.format_exc())
        return 1

    log("PASS")
    return 0
