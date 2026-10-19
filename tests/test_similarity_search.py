"""Find similar must say *why* it found nothing.

Two cases reported "No similar images found. Try lowering the minimum
similarity threshold", where no threshold could help:

- the comparison folder ({workspace}/_past_printed) was missing or empty —
  exactly the state of a fresh install, as a clean Windows Sandbox showed;
- the search raised: the worker printed to a console the packaged app does not
  have and emitted an empty result, indistinguishable from "no matches".
"""

import pytest

from src.services.image_similarity_service import (
    SimilaritySearchWorker, comparison_directory_problem, list_images)

FORMATS = [".jpg", ".png"]


class TestComparisonDirectoryProblem:
    def test_missing_folder_is_named(self, tmp_path):
        missing = tmp_path / "_past_printed"
        problem = comparison_directory_problem(str(missing), FORMATS)
        assert problem and "does not exist" in problem and str(missing) in problem

    def test_folder_without_photos_is_named(self, tmp_path):
        (tmp_path / "notes.txt").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.jpg").write_text("")  # top level only
        problem = comparison_directory_problem(str(tmp_path), FORMATS)
        assert problem and "no photos" in problem

    def test_folder_with_a_photo_is_fine(self, tmp_path):
        (tmp_path / "printed.JPG").write_text("")  # extension case ignored
        assert comparison_directory_problem(str(tmp_path), FORMATS) is None


def test_list_images_is_top_level_and_filtered(tmp_path):
    (tmp_path / "a.jpg").write_text("")
    (tmp_path / "b.PNG").write_text("")
    (tmp_path / "c.txt").write_text("")
    (tmp_path / "d.jpg").mkdir()  # a folder, not a photo
    names = sorted(p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                   for p in list_images(str(tmp_path), FORMATS))
    assert names == ["a.jpg", "b.PNG"]


class _Service:
    def __init__(self, error=None):
        self.error = error

    def load_images_from_directory(self, *_args, **_kwargs):
        if self.error:
            raise self.error
        return []

    def find_similar_images(self, *_args, **_kwargs):
        return []


def _run(qapp, service):
    worker = SimilaritySearchWorker(service, object(), "/cmp", FORMATS)
    completed, failed = [], []
    worker.search_complete.connect(completed.append)
    worker.search_failed.connect(failed.append)
    worker.run()  # synchronously: no thread to race
    return completed, failed


def test_a_failing_search_reports_the_error(qapp):
    completed, failed = _run(qapp, _Service(OSError("disk on fire")))
    assert failed == ["OSError: disk on fire"]
    assert completed == [], "a failure must not look like an empty result"


def test_a_search_with_no_matches_still_completes(qapp):
    completed, failed = _run(qapp, _Service())
    assert completed == [[]] and failed == []
