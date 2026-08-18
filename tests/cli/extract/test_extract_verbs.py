"""Tests for the public ``gaia extract`` verbs.

Every HTTP call is mocked by replacing ``_lkm_runtime.LKMClient`` with a fake
context manager whose ``.request`` / ``.request_multipart`` return canned
envelopes (or raise a typed transport / no-key error). No real LKM endpoint is
contacted.

Exit-code contract under test:
  0 ok / 1 business error / 2 transport / 3 no key / 4 arg validation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from gaia.cli import _lkm_runtime
from gaia.cli.commands.search.lkm._client import (
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _squash_ws(text: str) -> str:
    return " ".join(_ANSI_RE.sub("", text).split())


class _FakeClient:
    """Stand-in for ``LKMClient`` capturing calls and replaying responses."""

    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        raises: Exception | None = None,
    ):
        self._responses = responses if responses else [{"code": 0, "msg": "ok"}]
        self._raises = raises

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def _next(self) -> dict[str, Any]:
        if self._raises is not None:
            raise self._raises
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _FakeClient.calls.append(
            {"method": method, "path": path, "json_body": json_body, "params": params}
        )
        return self._next()

    def request_multipart(
        self,
        method: str,
        path: str,
        *,
        files: dict[str, tuple[str, Any, str]],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filename, handle, content_type = files["file"]
        _FakeClient.calls.append(
            {
                "method": method,
                "path": path,
                "filename": filename,
                "content_type": content_type,
                "body": handle.read(),
                "data": data,
            }
        )
        return self._next()


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[dict[str, Any]] | None = None,
    raises: Exception | None = None,
) -> None:
    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        if isinstance(raises, NoAccessKeyError):
            raise raises
        return _FakeClient(responses=responses, raises=raises)

    monkeypatch.setattr(_lkm_runtime, "LKMClient", factory)
    _FakeClient.calls = []


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.7 body")
    return path


_QUEUED = {"code": 0, "data": {"task_id": "task-1", "status": "queued", "cache_hit": False}}


class TestDocs:
    def test_extract_help_separates_extraction_from_retrieval(self) -> None:
        result = runner.invoke(app, ["extract", "--help"])

        assert result.exit_code == 0, result.output
        stdout = _squash_ws(result.stdout)
        assert "knowledge extraction, not layout parsing" in stdout
        assert "succeeded, partial, and failed" in stdout
        assert "0 ok / 1 business error / 2 transport / 3 no key / 4 bad args" in stdout

    def test_prints_endpoint_and_cli_reference_links(self) -> None:
        result = runner.invoke(app, ["extract", "docs"])

        assert result.exit_code == 0, result.output
        assert "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84" in result.stdout
        assert "POST /parse/task" in result.stdout
        assert "GET /parse/task/{task_id}/result" in result.stdout
        assert "docs/reference/cli/extract.md" in result.stdout


class TestSubmit:
    def test_uploads_pdf_as_multipart_field_file(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(pdf)])

        assert result.exit_code == 0, result.output
        call = _FakeClient.calls[0]
        assert call["method"] == "POST"
        assert call["path"] == "/parse/task"
        assert call["filename"] == "paper.pdf"
        assert call["content_type"] == "application/pdf"
        assert call["body"] == b"%PDF-1.7 body"
        assert json.loads(result.stdout)["data"]["task_id"] == "task-1"

    def test_emits_raw_json_with_polling_hint_on_stderr(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(pdf)])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == _QUEUED
        assert "gaia extract status task-1" in result.stderr

    def test_no_hint_suppresses_suggestion(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(pdf), "--no-hint"])

        assert result.exit_code == 0, result.output
        assert "gaia extract status" not in result.stderr

    @pytest.mark.parametrize(
        ("cache_source", "expected_detail"),
        [
            ("lkm", "already extracted in the LKM corpus"),
            ("local", "earlier submission of this same PDF"),
            (None, "Resubmitting a PDF reuses the existing extraction"),
        ],
    )
    def test_cache_hit_points_at_the_result_and_names_its_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pdf: Path,
        cache_source: str | None,
        expected_detail: str,
    ) -> None:
        data: dict[str, Any] = {"task_id": "task-1", "status": "succeeded", "cache_hit": True}
        if cache_source is not None:
            data["cache_source"] = cache_source
        _install_client(monkeypatch, responses=[{"code": 0, "data": data}])

        result = runner.invoke(app, ["extract", "submit", str(pdf)])

        assert result.exit_code == 0, result.output
        assert "gaia extract result task-1" in result.stderr
        assert expected_detail in result.stderr

    def test_out_writes_file(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path, tmp_path: Path
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])
        out = tmp_path / "nested" / "submit.json"

        result = runner.invoke(app, ["extract", "submit", str(pdf), "--out", str(out)])

        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text(encoding="utf-8")) == _QUEUED

    @pytest.mark.parametrize(
        ("name", "content", "expected"),
        [
            ("paper.txt", b"%PDF-1.7", "must be a PDF file"),
            ("paper.pdf", b"not a pdf", "valid PDF header"),
            ("paper.pdf", b"", "is empty"),
        ],
    )
    def test_rejects_unusable_files_before_upload(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        name: str,
        content: bytes,
        expected: str,
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])
        path = tmp_path / name
        path.write_bytes(content)

        result = runner.invoke(app, ["extract", "submit", str(path)])

        assert result.exit_code == 4, result.output
        assert expected in result.output
        assert _FakeClient.calls == []

    def test_missing_file_exits_4(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(tmp_path / "absent.pdf")])

        assert result.exit_code == 4, result.output
        assert _FakeClient.calls == []

    def test_rejects_unknown_index_before_reading_the_pdf(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(pdf), "--index", "nope"])

        assert result.exit_code == 4, result.output
        assert "unknown LKM index" in result.output
        assert _FakeClient.calls == []

    def test_wait_polls_until_terminal(self, monkeypatch: pytest.MonkeyPatch, pdf: Path) -> None:
        _install_client(
            monkeypatch,
            responses=[
                _QUEUED,
                {"code": 0, "data": {"task_id": "task-1", "status": "running", "stage": "step1"}},
                {"code": 0, "data": {"task_id": "task-1", "status": "succeeded", "stage": "done"}},
            ],
        )

        result = runner.invoke(
            app,
            ["extract", "submit", str(pdf), "--wait", "--poll-interval", "1"],
        )

        assert result.exit_code == 0, result.output
        assert [call["path"] for call in _FakeClient.calls] == [
            "/parse/task",
            "/parse/task/task-1",
            "/parse/task/task-1",
        ]
        assert json.loads(result.stdout)["data"]["status"] == "succeeded"
        assert "gaia extract result task-1" in result.stderr

    def test_wait_reports_a_failed_task_as_a_business_error(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(
            monkeypatch,
            responses=[
                _QUEUED,
                {
                    "code": 0,
                    "data": {
                        "task_id": "task-1",
                        "status": "failed",
                        "stage": "step0",
                        "failed_reason": "no extractable content",
                    },
                },
            ],
        )

        result = runner.invoke(
            app,
            ["extract", "submit", str(pdf), "--wait", "--poll-interval", "1"],
        )

        assert result.exit_code == 1, result.output
        assert "no extractable content" in result.output
        # The final status payload is still emitted so callers keep the detail.
        assert json.loads(result.stdout)["data"]["stage"] == "step0"

    def test_wait_timeout_says_the_task_is_still_running(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path
    ) -> None:
        _install_client(
            monkeypatch,
            responses=[
                _QUEUED,
                {"code": 0, "data": {"task_id": "task-1", "status": "running"}},
            ],
        )

        result = runner.invoke(
            app,
            ["extract", "submit", str(pdf), "--wait", "--poll-interval", "1", "--timeout", "1"],
        )

        assert result.exit_code == 2, result.output
        assert "stopped waiting" in result.output
        assert "gaia extract status task-1" in result.output

    @pytest.mark.parametrize(
        "argv",
        [
            ["--poll-interval", "0.1"],
            ["--poll-interval", "600"],
            ["--timeout", "0"],
        ],
    )
    def test_rejects_out_of_range_polling_options(
        self, monkeypatch: pytest.MonkeyPatch, pdf: Path, argv: list[str]
    ) -> None:
        _install_client(monkeypatch, responses=[_QUEUED])

        result = runner.invoke(app, ["extract", "submit", str(pdf), "--wait", *argv])

        assert result.exit_code == 4, result.output
        assert _FakeClient.calls == []

    def test_no_key_exits_3(self, monkeypatch: pytest.MonkeyPatch, pdf: Path) -> None:
        _install_client(monkeypatch, raises=NoAccessKeyError("no key"))

        result = runner.invoke(app, ["extract", "submit", str(pdf)])

        assert result.exit_code == 3, result.output
        assert "No LKM access key configured" in result.output

    def test_transport_error_exits_2(self, monkeypatch: pytest.MonkeyPatch, pdf: Path) -> None:
        _install_client(monkeypatch, raises=LKMTransportError("connection reset"))

        result = runner.invoke(app, ["extract", "submit", str(pdf)])

        assert result.exit_code == 2, result.output
        assert "connection reset" in result.output


class TestStatus:
    def test_reads_the_task_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            responses=[
                {
                    "code": 0,
                    "data": {
                        "task_id": "task-1",
                        "status": "running",
                        "stage": "step2",
                        "step_durations": [{"step": "ocr", "duration_ms": 12300}],
                    },
                }
            ],
        )

        result = runner.invoke(app, ["extract", "status", "task-1"])

        assert result.exit_code == 0, result.output
        assert _FakeClient.calls == [
            {"method": "GET", "path": "/parse/task/task-1", "json_body": None, "params": None}
        ]
        payload = json.loads(result.stdout)["data"]
        assert payload["stage"] == "step2"
        # step_durations reaches stdout untouched; Gaia never reshapes LKM JSON.
        assert payload["step_durations"] == [{"step": "ocr", "duration_ms": 12300}]
        assert "gaia extract status task-1" in result.stderr

    def test_partial_hint_warns_it_is_not_a_full_graph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            responses=[{"code": 0, "data": {"task_id": "task-1", "status": "partial"}}],
        )

        result = runner.invoke(app, ["extract", "status", "task-1"])

        assert result.exit_code == 0, result.output
        assert "not a full graph" in result.stderr
        assert "gaia extract result task-1" in result.stderr

    @pytest.mark.parametrize("task_id", ["../etc/passwd", "task 1", ""])
    def test_rejects_unsafe_task_ids(self, monkeypatch: pytest.MonkeyPatch, task_id: str) -> None:
        _install_client(monkeypatch)

        result = runner.invoke(app, ["extract", "status", task_id])

        assert result.exit_code == 4, result.output
        assert _FakeClient.calls == []


class TestResult:
    def test_fetches_the_flat_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "code": 0,
            "data": {
                "variables": [{"local_id": "paper:6::P1", "type": "claim", "global_id": None}],
                "factors": [],
                "motivations": [],
                "stats": {"variables_total": 1},
            },
        }
        _install_client(monkeypatch, responses=[payload])

        result = runner.invoke(app, ["extract", "result", "task-1"])

        assert result.exit_code == 0, result.output
        assert _FakeClient.calls == [
            {
                "method": "GET",
                "path": "/parse/task/task-1/result",
                "json_body": None,
                "params": None,
            }
        ]
        assert json.loads(result.stdout) == payload

    def test_not_ready_is_a_business_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            responses=[{"code": 290017, "msg": "parse result not ready"}],
        )

        result = runner.invoke(app, ["extract", "result", "task-1"])

        assert result.exit_code == 1, result.output
        assert "parse result not ready" in result.output

    def test_out_writes_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        payload = {"code": 0, "data": {"variables": [], "factors": []}}
        _install_client(monkeypatch, responses=[payload])
        out = tmp_path / "result.json"

        result = runner.invoke(app, ["extract", "result", "task-1", "--out", str(out)])

        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text(encoding="utf-8")) == payload
