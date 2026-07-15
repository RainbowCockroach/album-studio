"""Tests for src/services/image_processor.py.

Covers EXIF date reading (with a real embedded EXIF tag), the info dict, and the
date-based rename with duplicate-timestamp handling. HEIC-specific paths and the
Qt/orientation file mutations are out of scope.
"""

import os
from datetime import datetime

import piexif
from PIL import Image

from src.models.image_item import ImageItem
from src.models.project import Project
from src.services.image_processor import ImageProcessor


def write_jpeg_with_date(path, date_str="2023:12:25 14:30:22"):
    """Write a JPEG carrying an EXIF DateTimeOriginal tag."""
    exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode()}}
    exif_bytes = piexif.dump(exif_dict)
    Image.new("RGB", (16, 16), (10, 20, 30)).save(str(path), "JPEG", exif=exif_bytes)


class TestReadExifDate:
    def test_reads_embedded_datetime_original(self, tmp_path):
        p = tmp_path / "photo.jpg"
        write_jpeg_with_date(p)
        assert ImageProcessor.read_exif_date(str(p)) == datetime(2023, 12, 25, 14, 30, 22)

    def test_no_exif_falls_back_to_mtime(self, tmp_path):
        p = tmp_path / "plain.jpg"
        Image.new("RGB", (16, 16)).save(str(p), "JPEG")
        result = ImageProcessor.read_exif_date(str(p))
        # falls back to file modification time → still a datetime, never None
        assert isinstance(result, datetime)


class TestGetExifInfo:
    def test_returns_core_fields(self, tmp_path):
        p = tmp_path / "photo.jpg"
        Image.new("RGB", (32, 24)).save(str(p), "JPEG")
        info = ImageProcessor.get_exif_info(str(p))
        assert info["Filename"] == "photo.jpg"
        assert info["Dimensions"] == "32 x 24"
        assert info["Format"] == "JPEG"
        assert "Size" in info and info["Size"].endswith("MB")
        assert "Date Modified" in info


class TestRenameByDate:
    def test_renames_using_date_taken(self, tmp_path):
        src = tmp_path / "IMG_1234.jpg"
        Image.new("RGB", (8, 8)).save(str(src), "JPEG")

        item = ImageItem(str(src))
        item.date_taken = datetime(2023, 12, 25, 14, 30, 22)
        project = Project("p", str(tmp_path), str(tmp_path / "out"))
        project.images = [item]

        count = ImageProcessor.rename_by_date(project)
        assert count == 1
        expected = tmp_path / "20231225_143022.jpg"
        assert expected.exists()
        assert item.file_path == str(expected)

    def test_duplicate_timestamps_get_counter_suffix(self, tmp_path):
        items = []
        for i in range(2):
            src = tmp_path / f"orig_{i}.jpg"
            Image.new("RGB", (8, 8)).save(str(src), "JPEG")
            it = ImageItem(str(src))
            it.date_taken = datetime(2023, 12, 25, 14, 30, 22)  # identical
            items.append(it)
        project = Project("p", str(tmp_path), str(tmp_path / "out"))
        project.images = items

        count = ImageProcessor.rename_by_date(project)
        assert count == 2
        names = sorted(os.path.basename(i.file_path) for i in items)
        # first keeps the plain timestamp, second gets a _1 suffix
        assert names == ["20231225_143022.jpg", "20231225_143022_1.jpg"]

    def test_skips_images_without_date(self, tmp_path, monkeypatch):
        src = tmp_path / "nodate.jpg"
        Image.new("RGB", (8, 8)).save(str(src), "JPEG")
        item = ImageItem(str(src))
        # force read_exif_date to yield None (no date available at all)
        monkeypatch.setattr(
            "src.services.image_processor.ImageProcessor.read_exif_date",
            staticmethod(lambda _path: None),
        )
        project = Project("p", str(tmp_path), str(tmp_path / "out"))
        project.images = [item]

        assert ImageProcessor.rename_by_date(project) == 0
        assert src.exists()  # untouched
