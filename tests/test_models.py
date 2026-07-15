"""Tests for the pure model logic in src/models (Project, ImageItem).

Qt is only imported, never driven — no QApplication or pixmaps are created.
"""

import os
from datetime import datetime

from src.models.image_item import ImageItem
from src.models.project import Project


class TestImageItemTags:
    def test_tag_helpers(self):
        item = ImageItem("/x/a.jpg")
        assert item.has_tags() is False
        assert item.is_fully_tagged() is False

        item.set_tags(album="A4")
        assert item.has_tags() is True
        assert item.is_fully_tagged() is False

        item.set_tags(size="9x6")
        assert item.is_fully_tagged() is True

    def test_clear_tags_also_clears_crop(self):
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        item.crop_box = {"x": 0, "y": 0, "width": 10, "height": 10}
        item.clear_tags()
        assert item.album_tag is None
        assert item.size_tag is None
        assert item.crop_box is None


class TestSetTagsCropBox:
    """A crop box is only meaningful for the ratio it was drawn against."""

    def test_changing_size_ratio_clears_crop_box(self):
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")  # 3:2
        item.crop_box = {"x": 0, "y": 0, "width": 600, "height": 400}

        item.set_tags(size="6x6")  # 1:1 — the old box is now the wrong shape

        assert item.crop_box is None

    def test_same_ratio_keeps_crop_box(self):
        """The box stays valid across tags that mean the same ratio.

        Pins the other half of the BUG-4 fix: 9x6 and 12x8 are both 3:2, so
        clearing on a bare tag-string comparison would throw away good work.
        """
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        box = {"x": 0, "y": 0, "width": 600, "height": 400}
        item.crop_box = box

        item.set_tags(size="12x8")

        assert item.crop_box == box

    def test_retagging_same_size_keeps_crop_box(self):
        """Re-clicking the same tag must not silently discard a manual crop."""
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        box = {"x": 10, "y": 20, "width": 600, "height": 400}
        item.crop_box = box

        item.set_tags(album="A4", size="9x6")

        assert item.crop_box == box

    def test_album_only_change_keeps_crop_box(self):
        """Moving a photo between albums does not change its shape."""
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        box = {"x": 10, "y": 20, "width": 600, "height": 400}
        item.crop_box = box

        item.set_tags(album="A5")

        assert item.crop_box == box

    def test_unparseable_size_clears_crop_box(self):
        """An unprovable ratio is treated as a different one.

        parse_size_ratio raises on a name it cannot read, so neither side of the
        comparison can be trusted — dropping the box costs a re-drag, keeping it
        risks a stretched print.
        """
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        item.crop_box = {"x": 0, "y": 0, "width": 600, "height": 400}

        item.set_tags(size="Panorama")

        assert item.crop_box is None


class TestImageItemSerialization:
    def test_round_trip(self):
        item = ImageItem("/x/a.jpg")
        item.set_tags(album="A4", size="9x6")
        item.is_cropped = True
        item.crop_box = {"x": 1, "y": 2, "width": 3, "height": 4}
        item.add_date_stamp = True
        item.date_taken = datetime(2026, 6, 15, 9, 30, 0)

        restored = ImageItem.from_dict(item.to_dict())
        assert restored.file_path == "/x/a.jpg"
        assert restored.album_tag == "A4"
        assert restored.size_tag == "9x6"
        assert restored.is_cropped is True
        assert restored.crop_box == {"x": 1, "y": 2, "width": 3, "height": 4}
        assert restored.add_date_stamp is True
        assert restored.date_taken == datetime(2026, 6, 15, 9, 30, 0)

    def test_from_dict_defaults(self):
        item = ImageItem.from_dict({"file_path": "/x/a.jpg"})
        assert item.album_tag is None
        assert item.is_cropped is False
        assert item.add_date_stamp is False
        assert item.date_taken is None


class TestGetDisplayDate:
    def test_parses_date_from_filename(self):
        item = ImageItem("/photos/20231225_143022.jpg")
        assert item.get_display_date() == datetime(2023, 12, 25, 14, 30, 22)

    def test_cached_exif_date_wins(self):
        item = ImageItem("/photos/20231225_143022.jpg")
        item.date_taken = datetime(2000, 1, 1, 0, 0, 0)
        assert item.get_display_date() == datetime(2000, 1, 1, 0, 0, 0)

    def test_invalid_filename_date_falls_back_to_mtime(self, make_image):
        # a real file with a non-date name → falls back to file mtime
        path = make_image(name="not_a_date.jpg")
        result = ImageItem(path).get_display_date()
        assert isinstance(result, datetime)

    def test_impossible_date_in_filename_ignored(self, make_image):
        # 13th month must not crash; falls through to mtime
        path = make_image(name="20231345_990000.jpg")
        result = ImageItem(path).get_display_date()
        assert isinstance(result, datetime)


class TestProject:
    def test_load_images_filters_by_format(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        from PIL import Image
        Image.new("RGB", (10, 10)).save(str(input_dir / "a.jpg"))
        Image.new("RGB", (10, 10)).save(str(input_dir / "b.png"))
        (input_dir / "notes.txt").write_text("ignore me")

        proj = Project("p", str(input_dir), str(tmp_path / "output"))
        proj.load_images([".jpg", ".png"])
        names = sorted(os.path.basename(i.file_path) for i in proj.images)
        assert names == ["a.jpg", "b.png"]

    def test_tagged_untagged_partitioning(self):
        proj = Project("p", "/in", "/out")
        a, b, c = ImageItem("/in/a.jpg"), ImageItem("/in/b.jpg"), ImageItem("/in/c.jpg")
        a.set_tags(album="A4", size="9x6")   # fully tagged
        b.set_tags(album="A4")               # partially tagged
        proj.images = [a, b, c]
        assert proj.get_tagged_images() == [a]
        assert proj.get_untagged_images() == [c]

    def test_dict_round_trip(self):
        proj = Project("p", "/in", "/out")
        item = ImageItem("/in/a.jpg")
        item.set_tags(album="A4", size="9x6")
        proj.images = [item]

        restored = Project.from_dict(proj.to_dict())
        assert restored.name == "p"
        assert restored.input_folder == "/in"
        assert len(restored.images) == 1
        assert restored.images[0].album_tag == "A4"

    def test_project_data_persistence_round_trip(self, tmp_path):
        data_dir = str(tmp_path / "data")
        proj = Project("p", "/in", "/out")
        tagged = ImageItem("/in/a.jpg")
        tagged.set_tags(album="A4", size="9x6")
        tagged.add_date_stamp = True
        untagged = ImageItem("/in/b.jpg")  # no tags → not persisted
        proj.images = [tagged, untagged]
        proj.save_project_data(data_dir)

        # a fresh project with the same image paths reloads the saved tags
        proj2 = Project("p", "/in", "/out")
        proj2.images = [ImageItem("/in/a.jpg"), ImageItem("/in/b.jpg")]
        proj2.load_project_data(data_dir)
        a2 = proj2.get_image_by_path("/in/a.jpg")
        assert a2 is not None
        assert a2.album_tag == "A4"
        assert a2.size_tag == "9x6"
        assert a2.add_date_stamp is True
        # the untagged image stayed untagged
        assert proj2.get_image_by_path("/in/b.jpg").album_tag is None
