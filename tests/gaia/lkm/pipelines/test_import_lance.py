"""Tests for pipelines/import_lance.py — Checkpoint + merge logic."""

import json
from pathlib import Path

from gaia.lkm.pipelines.import_lance import Checkpoint
from gaia.lkm.storage.source_lance import merge_xmls


class TestCheckpoint:
    def test_new_checkpoint(self, tmp_path):
        cp = Checkpoint(tmp_path / "cp.json")
        assert cp.status("paper1") is None

    def test_update_and_read(self, tmp_path):
        cp = Checkpoint(tmp_path / "cp.json")
        cp.update("paper1", "ingested")
        assert cp.status("paper1") == "ingested"

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "cp.json"
        cp1 = Checkpoint(path)
        cp1.update("paper1", "ingested")

        cp2 = Checkpoint(path)
        assert cp2.status("paper1") == "ingested"

    def test_pending_filters_ingested(self, tmp_path):
        cp = Checkpoint(tmp_path / "cp.json")
        cp.update("p1", "ingested")
        cp.update("p2", "failed:download")

        pending = cp.pending(["p1", "p2", "p3"])
        assert pending == ["p2", "p3"]


class TestMergeXmls:
    def test_merge_single(self):
        xml = '<premise name="x">content</premise>'
        result = merge_xmls([xml])
        assert result == "<inference_unit><premise name=\"x\">content</premise></inference_unit>"

    def test_merge_multiple(self):
        xmls = [
            '<?xml version="1.0" encoding="UTF-8"?>\n<premise id="1">a</premise>',
            '<?xml version="1.0" encoding="UTF-8"?>\n<!-- comment -->\n<premise id="2">b</premise>',
        ]
        result = merge_xmls(xmls)
        assert "<premise id=\"1\">a</premise>" in result
        assert "<premise id=\"2\">b</premise>" in result
        assert "<?xml" not in result
        assert "<!-- comment -->" not in result

    def test_merge_empty(self):
        assert merge_xmls([]) == "<inference_unit></inference_unit>"


