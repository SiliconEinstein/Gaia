"""Tests for the public ``gaia search lkm`` verbs.

Every HTTP call is mocked by replacing ``_shared.LKMClient`` with a fake
context manager whose ``.request`` returns a canned envelope (or raises a
typed transport / no-key error). No real LKM endpoint is contacted.

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

from gaia.cli._credentials import CredentialPermissionError
from gaia.cli.commands.search.lkm import _shared
from gaia.cli.commands.search.lkm._client import (
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class _FakeClient:
    """Stand-in for ``LKMClient`` capturing the last request."""

    last_call: ClassVar[dict[str, Any]] = {}
    last_init_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self, response: dict[str, Any] | None = None, raises: Exception | None = None):
        self._response = response if response is not None else {"code": 0, "msg": "ok"}
        self._raises = raises

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _FakeClient.last_call = {
            "method": method,
            "path": path,
            "json_body": json_body,
            "params": params,
        }
        if self._raises is not None:
            raise self._raises
        return self._response


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: dict[str, Any] | None = None,
    raises: Exception | None = None,
) -> None:
    """Patch ``_shared.LKMClient`` so verbs use the fake (no key required)."""

    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        if raises is not None and isinstance(raises, NoAccessKeyError):
            raise raises
        _FakeClient.last_init_kwargs = dict(_kwargs)
        return _FakeClient(response=response, raises=raises)

    monkeypatch.setattr(_shared, "LKMClient", factory)
    _FakeClient.last_call = {}
    _FakeClient.last_init_kwargs = {}


def _install_constructor_error(monkeypatch: pytest.MonkeyPatch, raises: Exception) -> None:
    """Patch ``_shared.LKMClient`` to fail during construction."""

    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        raise raises

    monkeypatch.setattr(_shared, "LKMClient", factory)
    _FakeClient.last_call = {}


# --------------------------------------------------------------------------- #
# docs                                                                        #
# --------------------------------------------------------------------------- #


class TestDocs:
    def test_prints_lkm_api_and_cli_reference_links(self) -> None:
        result = runner.invoke(app, ["search", "lkm", "docs"])

        assert result.exit_code == 0, result.output
        assert "LKM API docs:" in result.stdout
        assert "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84" in result.stdout
        assert "POST /search" in result.stdout
        assert "POST /reasoning/search" in result.stdout
        assert "GET /claims/{id}/reasoning" in result.stdout
        assert "POST /variables/batch" in result.stdout
        assert "POST /papers/graph" in result.stdout
        assert "CLI reference:" in result.stdout
        assert "docs/reference/cli/search.md" in result.stdout

    @pytest.mark.parametrize(
        ("argv", "expected_urls"),
        [
            (
                ["search", "lkm", "knowledge", "--help"],
                ["https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459806352"],
            ),
            (
                ["search", "lkm", "reasoning", "--help"],
                [
                    "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807117",
                    "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807347",
                ],
            ),
            (
                ["search", "lkm", "nodes", "--help"],
                ["https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459805971"],
            ),
            (
                ["search", "lkm", "package", "--help"],
                ["https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459808997"],
            ),
        ],
    )
    def test_subcommand_help_prints_endpoint_specific_docs(
        self, argv: list[str], expected_urls: list[str]
    ) -> None:
        result = runner.invoke(app, argv)

        assert result.exit_code == 0, result.output
        for url in expected_urls:
            assert url in result.stdout


# --------------------------------------------------------------------------- #
# knowledge                                                                   #
# --------------------------------------------------------------------------- #


class TestKnowledge:
    def test_help_recommends_reasoning_only_for_conclusions(self) -> None:
        result = runner.invoke(app, ["search", "lkm", "knowledge", "--help"])

        assert result.exit_code == 0, result.output
        stdout = _strip_ansi(result.stdout)
        assert "--reasoning-only" in stdout
        assert "conclusions" in stdout

    def test_happy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(app, ["search", "lkm", "knowledge", "perovskite"])
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["query"] == "perovskite"
        assert body["retrieval_mode"] == "hybrid"
        assert body["filters"] == {"visibility": "public"}

    def test_default_emits_raw_json_with_gaia_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "code": 0,
            "data": {
                "variables": [
                    {
                        "id": "gcn_579430355a0e4bbd",
                        "type": "claim",
                        "has_reasoning": True,
                        "provenance": {
                            "source_packages": ["paper:811827932371615744"],
                        },
                    }
                ]
            },
        }
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "knowledge", "perovskite"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "gaia search lkm reasoning --index bohrium --claim-id gcn_579430355a0e4bbd" in (
            result.stderr
        )
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_no_hint_suppresses_gaia_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"code": 0, "data": {"variables": [{"id": "gcn_1", "type": "claim"}]}}
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "knowledge", "q", "--no-hint"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_accepts_default_server_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "perovskite", "--server", "BOHRIUM"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0

    def test_accepts_index_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "perovskite", "--index", "BOHRIUM"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0

    def test_index_url_can_come_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_INDEX_PRIVATE_URL", "https://example.test/lkm")
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "perovskite", "--index", "private"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0
        assert _FakeClient.last_init_kwargs == {"base_url": "https://example.test/lkm"}

    def test_index_id_normalizes_underscore_to_dash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GAIA_LKM_INDEX_PRIVATE_INDEX_URL", "https://example.test/lkm")
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "perovskite", "--index", "private_index"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0
        assert _FakeClient.last_init_kwargs == {"base_url": "https://example.test/lkm"}

    def test_rejects_unknown_server_before_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "q", "--server", "private-lkm"],
        )
        assert result.exit_code == 4, result.output
        assert "unknown LKM index" in result.output
        assert _FakeClient.last_call == {}

    def test_options_build_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "q",
                "--scopes",
                "claim",
                "--retrieval-mode",
                "lexical",
                "--keywords",
                "a",
                "--keywords",
                "b",
                "--reasoning-only",
                "--role",
                "conclusion",
                "--include-paper-enrich",
                "--offset",
                "5",
                "--limit",
                "3",
            ],
        )
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["scopes"] == ["claim"]
        assert body["retrieval_mode"] == "lexical"
        assert body["keywords"] == ["a", "b"]
        assert body["reasoning_only"] is True
        assert body["include_paper_enrich"] is True
        assert body["filters"]["role"] == "conclusion"
        assert body["offset"] == 5 and body["limit"] == 3

    def test_allows_claim_and_question_scopes_without_reasoning_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "q",
                "--scopes",
                "claim",
                "--scopes",
                "question",
            ],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["scopes"] == ["claim", "question"]

    def test_rejects_reasoning_only_with_question_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "q",
                "--scopes",
                "question",
                "--reasoning-only",
            ],
        )
        assert result.exit_code == 4, result.output
        assert "reasoning-only" in result.output
        assert _FakeClient.last_call == {}

    def test_rejects_retired_action_scope_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q", "--scopes", "action"])
        assert result.exit_code != 0, result.output
        assert _FakeClient.last_call == {}

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290002, "msg": "bad params"})
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 1, result.output
        assert "290002" in result.output

    def test_transport_error_exits_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=LKMTransportError("boom"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 2, result.output

    def test_no_key_exits_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=NoAccessKeyError("no key"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 3, result.output

    def test_credential_permission_error_exits_2_without_traceback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_constructor_error(monkeypatch, CredentialPermissionError("bad mode"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 2, result.output
        assert "bad mode" in result.output
        assert "Traceback" not in result.output

    def test_too_many_keywords_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        args = ["search", "lkm", "knowledge", "q"]
        for i in range(11):
            args += ["--keywords", f"k{i}"]
        result = runner.invoke(app, args)
        assert result.exit_code == 4, result.output

    def test_limit_out_of_range_exits_4_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q", "--limit", "101"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_offset_out_of_range_exits_4_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q", "--offset", "-1"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_nested_error_message_is_rendered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={"code": 290001, "error": {"msg": "context deadline exceeded"}},
        )
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 1, result.output
        assert "context deadline exceeded" in result.output

    def test_out_writes_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        payload = {"code": 0, "msg": "ok", "n": 1}
        _install_client(monkeypatch, response=payload)
        dest = tmp_path / "nested" / "out.json"
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "q", "--out", str(dest)],
        )
        assert result.exit_code == 0, result.output
        assert result.stdout == ""
        assert json.loads(dest.read_text()) == payload

    def test_claim_without_reasoning_has_no_inspect_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "variables": [
                        {
                            "content": "A standalone extracted claim.",
                            "has_reasoning": False,
                            "id": "gcn_no_reasoning",
                            "title": "Standalone claim",
                            "type": "claim",
                        }
                    ],
                },
            },
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "standalone"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["variables"][0]["id"] == "gcn_no_reasoning"
        assert "gaia search lkm reasoning" not in result.stderr

    def test_claim_without_reasoning_flag_has_no_inspect_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "variables": [
                    {
                        "id": "gcn_unknown_reasoning",
                        "type": "claim",
                        "provenance": {"source_packages": ["paper:811827932371615744"]},
                    }
                ],
            },
        }
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "knowledge", "standalone"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "gaia search lkm reasoning" not in result.stderr
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_single_question_scope_dispatches_query_kind_to_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch, response={"code": 0, "data": {"variables": []}})

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "open problem",
                "--scopes",
                "question",
            ],
        )

        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["scopes"] == ["question"]


# --------------------------------------------------------------------------- #
# reasoning                                                                   #
# --------------------------------------------------------------------------- #


class TestReasoning:
    def test_fetches_claim_reasoning_by_claim_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "gcn_abc123"],
        )
        assert result.exit_code == 0, result.output
        call = _FakeClient.last_call
        assert call["method"] == "GET"
        assert call["path"] == "/claims/gcn_abc123/reasoning"
        assert call["params"] == {
            "format": "graph",
            "max_chains": 10,
            "sort_by": "comprehensive",
        }

    def test_prefixed_claim_id_strips_prefix_and_infers_index(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The prefixed `lkm:<index>:gcn_…` form (as printed) is accepted."""
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "--claim-id",
                "lkm:bohrium:gcn_abc123",
            ],
        )
        assert result.exit_code == 0, result.output
        call = _FakeClient.last_call
        assert call["path"] == "/claims/gcn_abc123/reasoning"
        assert json.loads(result.stdout)["code"] == 0

    def test_prefixed_positional_claim_id_routes_to_claim_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare positional in the prefixed form also routes to --claim-id mode."""
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "lkm:bohrium:gcn_abc123"],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["path"] == "/claims/gcn_abc123/reasoning"

    def test_prefixed_claim_id_with_matching_index_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "--index",
                "bohrium",
                "--claim-id",
                "lkm:bohrium:gcn_abc123",
            ],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["path"] == "/claims/gcn_abc123/reasoning"

    def test_prefixed_claim_id_index_disagreement_exits_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "--index",
                "bohrium",
                "--claim-id",
                "lkm:other:gcn_abc123",
            ],
        )
        assert result.exit_code == 4, result.output
        assert "disagrees" in result.output

    def test_fetches_claim_reasoning_with_server_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "--server",
                "bohrium",
                "--claim-id",
                "gcn_abc123",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0
        assert _FakeClient.last_call["path"] == "/claims/gcn_abc123/reasoning"

    def test_positional_claim_id_fetches_claim_reasoning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [], "total_chains": 0},
            },
        )
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "gcn_abc123",
                "--max-chains",
                "3",
            ],
        )
        assert result.exit_code == 0, result.output
        call = _FakeClient.last_call
        assert call["method"] == "GET"
        assert call["path"] == "/claims/gcn_abc123/reasoning"
        assert call["params"] == {
            "format": "graph",
            "max_chains": 3,
            "sort_by": "comprehensive",
        }

    def test_query_search_calls_reasoning_search_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "thermal stability"],
        )
        assert result.exit_code == 0, result.output
        call = _FakeClient.last_call
        assert call["method"] == "POST"
        assert call["path"] == "/reasoning/search"
        assert call["json_body"]["query"] == "thermal stability"
        assert call["json_body"]["format"] == "graph"

    def test_url_encodes_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok"})
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "a/b c"],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["path"] == "/claims/a%2Fb%20c/reasoning"

    def test_raw_json_keeps_nested_reasoning_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [{"id": 1}], "total_chains": 1},
            },
        )
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "x"],
        )
        assert result.exit_code == 0, result.output
        out = json.loads(result.stdout)
        assert out["data"]["reasoning_chains"] == [{"id": 1}]
        assert out["data"]["total_chains"] == 1
        assert "reasoning_chains" not in out

    def test_max_chains_out_of_range_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "x", "--max-chains", "101"],
        )
        assert result.exit_code == 4, result.output

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290004, "msg": "claim not found"})
        result = runner.invoke(app, ["search", "lkm", "reasoning", "--claim-id", "x"])
        assert result.exit_code == 1, result.output

    def test_rejects_query_and_claim_id_together(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "q", "--claim-id", "gcn_abc123"],
        )
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_rejects_claim_options_in_query_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "reasoning", "q", "--max-chains", "5"])
        assert result.exit_code == 4, result.output
        assert "--max-chains" in result.output
        assert _FakeClient.last_call == {}

    def test_rejects_query_options_in_claim_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "gcn_abc123", "--limit", "5"],
        )
        assert result.exit_code == 4, result.output
        assert "--limit" in result.output
        assert _FakeClient.last_call == {}

    def test_claim_reasoning_emits_raw_json_with_paper_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "reasoning_chains": [
                    {
                        "source_package": "paper:811827932371615744",
                        "graph": {"nodes": [], "edges": []},
                    }
                ]
            },
        }
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "reasoning", "--claim-id", "gcn_result"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_claim_reasoning_without_paper_hints_claim_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"code": 0, "data": {"reasoning_chains": []}}
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "reasoning", "--claim-id", "gcn_result"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "gaia pkg add --lkm-index bohrium --lkm-claim gcn_result" in result.stderr

    def test_query_reasoning_emits_raw_json_with_paper_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "reasoning_chains": [
                        {
                            "source_package": "paper:811",
                            "graph": {
                                "nodes": [
                                    {
                                        "id": "paper:811::question",
                                        "type": "question",
                                        "kind": "subproblem",
                                        "content": "Why does the model work?",
                                    },
                                    {
                                        "id": "gcn_prev",
                                        "type": "claim",
                                        "kind": "conclusion",
                                        "title": "Previous result",
                                    },
                                    {
                                        "id": "gcn_weak",
                                        "type": "claim",
                                        "kind": "weak_point",
                                        "title": "Known limitation",
                                    },
                                    {
                                        "id": "gcn_highlight",
                                        "type": "claim",
                                        "kind": "highlight",
                                        "title": "Key observation",
                                    },
                                    {
                                        "id": "lfac_1",
                                        "type": "factor",
                                        "kind": "reasoning_steps",
                                        "steps": [{"reasoning": "Combine the evidence."}],
                                    },
                                    {
                                        "id": "gcn_result",
                                        "type": "claim",
                                        "kind": "conclusion",
                                        "title": "Final result",
                                    },
                                ],
                                "edges": [
                                    {
                                        "type": "subproblem_of",
                                        "source": "paper:811::question",
                                        "target": "gcn_result",
                                    },
                                    {
                                        "type": "previous_conclusion_of",
                                        "source": "gcn_prev",
                                        "target": "lfac_1",
                                    },
                                    {
                                        "type": "weakpoint_of",
                                        "source": "gcn_weak",
                                        "target": "lfac_1",
                                    },
                                    {
                                        "type": "highlight_of",
                                        "source": "gcn_highlight",
                                        "target": "lfac_1",
                                    },
                                    {
                                        "type": "concludes",
                                        "source": "lfac_1",
                                        "target": "gcn_result",
                                    },
                                ],
                            },
                        }
                    ]
                },
            },
        )

        result = runner.invoke(app, ["search", "lkm", "reasoning", "thermal stability"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["reasoning_chains"][0]["source_package"] == (
            "paper:811"
        )
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811" in result.stderr


# --------------------------------------------------------------------------- #
# nodes                                                                       #
# --------------------------------------------------------------------------- #


class TestNodes:
    def test_happy_dedupe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "nodes", "a", "b", "a"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a", "b"]}

    def test_accepts_server_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "nodes", "a", "--server", "bohrium"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a"]}

    def test_accepts_index_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "nodes", "a", "--index", "bohrium"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a"]}

    def test_merge_with_ids_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _install_client(monkeypatch)
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("b\nc\n\n", encoding="utf-8")
        result = runner.invoke(
            app, ["search", "lkm", "nodes", "a", "b", "--ids-file", str(ids_file)]
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a", "b", "c"]}

    def test_empty_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "nodes"])
        assert result.exit_code == 4, result.output

    def test_missing_ids_file_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app, ["search", "lkm", "nodes", "a", "--ids-file", "/nonexistent/x.txt"]
        )
        assert result.exit_code == 4, result.output

    def test_no_key_exits_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=NoAccessKeyError("no key"))
        result = runner.invoke(app, ["search", "lkm", "nodes", "a"])
        assert result.exit_code == 3, result.output


# --------------------------------------------------------------------------- #
# package                                                                     #
# --------------------------------------------------------------------------- #


class TestPackage:
    def test_happy_default_uses_latest_graph_response_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "package", "--paper-id", "p1"])
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["paper_id"] == "p1"
        assert "include" not in body

    def test_accepts_server_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--server", "bohrium", "--paper-id", "p1"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0
        assert "gaia pkg add --lkm-index bohrium --lkm-paper p1" in result.stderr

    def test_accepts_index_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--index", "bohrium", "--paper-id", "p1"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["code"] == 0
        assert "gaia pkg add --lkm-index bohrium --lkm-paper p1" in result.stderr

    def test_no_identifier_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "package"])
        assert result.exit_code == 4, result.output

    def test_two_identifiers_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "package", "--paper-id", "p1", "--doi", "d1"])
        assert result.exit_code == 4, result.output

    def test_title_resolve_limit_with_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--title", "t", "--title-resolve-limit", "7"],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["title_resolve"] == {"limit": 7}

    def test_title_resolve_limit_without_title_exits_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--paper-id", "p1", "--title-resolve-limit", "7"],
        )
        assert result.exit_code == 4, result.output

    def test_title_resolve_limit_out_of_range_exits_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--title", "t", "--title-resolve-limit", "21"],
        )
        assert result.exit_code == 4, result.output

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290011, "msg": "not found"})
        result = runner.invoke(app, ["search", "lkm", "package", "--doi", "d"])
        assert result.exit_code == 1, result.output

    def test_default_emits_raw_paper_graph_with_package_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": [
                    {
                        "paper": {
                            "doi": "10.1016/j.jpcs.2021.110374",
                            "en_abstract": "A facile all-dip-coating deposition is proposed.",
                            "en_title": "Controlling phase and morphology",
                            "id": "811827932371615744",
                            "package_id": "paper:811827932371615744",
                        },
                        "stats": {
                            "factors_total": 2,
                            "variables_total": 25,
                        },
                        "addressed_problems": [
                            {
                                "id": "paper:811827932371615744::problem_1",
                                "global_id": "gp_phase_stability",
                                "content": "How can phase stability be controlled?",
                            }
                        ],
                        "open_questions": [
                            {
                                "id": "paper:811827932371615744::open_1",
                                "global_id": "gq_stability_mechanisms",
                                "content": "Which stability mechanisms remain unresolved?",
                            }
                        ],
                        "graph": {
                            "nodes": [
                                {
                                    "id": "paper:811827932371615744::conclusion_1_subproblem",
                                    "type": "question",
                                    "kind": "subproblem",
                                    "content": (
                                        "Which local condition supports the phase-stability "
                                        "conclusion?"
                                    ),
                                },
                                {
                                    "id": "paper:811827932371615744::conclusion_1",
                                    "type": "claim",
                                    "kind": "conclusion",
                                    "title": "Annealing controls phase stability",
                                },
                                {
                                    "id": "paper:811827932371615744::highlight_1",
                                    "type": "claim",
                                    "kind": "highlight",
                                    "content": "120 C gives the best alpha phase.",
                                },
                                {
                                    "id": "lfac_1",
                                    "type": "factor",
                                    "kind": "reasoning_steps",
                                },
                            ],
                            "edges": [
                                {
                                    "type": "subproblem_of",
                                    "source": ("paper:811827932371615744::conclusion_1_subproblem"),
                                    "target": "paper:811827932371615744::conclusion_1",
                                },
                                {
                                    "type": "highlight_of",
                                    "source": "paper:811827932371615744::highlight_1",
                                    "target": "lfac_1",
                                },
                                {
                                    "type": "concludes",
                                    "source": "lfac_1",
                                    "target": "paper:811827932371615744::conclusion_1",
                                },
                            ],
                        },
                    }
                ]
            },
        }
        _install_client(
            monkeypatch,
            response=payload,
        )

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "package",
                "--paper-id",
                "811827932371615744",
            ],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "results" not in json.loads(result.stdout)
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_raw_paper_graph_preserves_problem_refs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": [
                    {
                        "paper": {
                            "en_title": "Problem refs",
                            "id": "811827932371615744",
                            "package_id": "paper:811827932371615744",
                        },
                        "addressed_problems": [
                            {
                                "id": "paper:811827932371615744::problem_1",
                                "global_id": "gp_1",
                                "content": "Full problem statement.",
                            },
                            {"content": "Problem without ids."},
                            {"score": 0.5},
                            "not-a-dict",
                        ],
                        "open_questions": [{"global_id": "gq_1", "content": "Remaining question."}],
                        "graph": {"nodes": [], "edges": []},
                    }
                ]
            },
        }
        _install_client(
            monkeypatch,
            response=payload,
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--paper-id", "811827932371615744"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload

    def test_raw_package_preserves_dict_shaped_wrapped_paper_graph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": {
                    "paper:811827932371615744": {
                        "paper": {
                            "en_title": "Dict shaped paper",
                            "id": "811827932371615744",
                            "package_id": "paper:811827932371615744",
                        },
                        "graph": {
                            "nodes": [
                                {"id": "gcn_result", "type": "claim"},
                                {"id": "lfac_1", "type": "factor"},
                            ],
                            "edges": [
                                {
                                    "type": "concludes",
                                    "source": "lfac_1",
                                    "target": "gcn_result",
                                }
                            ],
                        },
                        "stats": {"variables_total": 2},
                    }
                }
            },
        }
        _install_client(
            monkeypatch,
            response=payload,
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--paper-id", "811827932371615744"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_title_result_without_paper_id_has_no_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": [
                    {
                        "paper": {
                            "en_title": "Unresolved paper candidate",
                        },
                        "stats": {"variables_total": 1},
                    }
                ]
            },
        }
        _install_client(
            monkeypatch,
            response=payload,
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--title", "ambiguous candidate"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_title_result_with_multiple_papers_has_no_materialize_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": [
                    {"paper": {"id": "811111111111111111"}},
                    {"paper": {"id": "822222222222222222"}},
                ]
            },
        }
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--title", "ambiguous candidate"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_no_hint_suppresses_package_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"code": 0, "msg": "ok"}
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(
            app,
            ["search", "lkm", "package", "--paper-id", "811827932371615744", "--no-hint"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_out_writes_raw_package_file_and_hint_to_stderr(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        payload = {"code": 0, "data": {"papers": []}}
        _install_client(monkeypatch, response=payload)
        dest = tmp_path / "nested" / "paper_graph.json"

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "package",
                "--paper-id",
                "811827932371615744",
                "--out",
                str(dest),
            ],
        )

        assert result.exit_code == 0, result.output
        assert result.stdout == ""
        assert json.loads(dest.read_text()) == payload
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)
