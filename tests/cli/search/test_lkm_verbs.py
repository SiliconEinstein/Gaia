"""Tests for the five ``gaia search lkm`` verbs.

Every HTTP call is mocked by replacing ``_shared.LKMClient`` with a fake
context manager whose ``.request`` returns a canned envelope (or raises a
typed transport / no-key error). No real LKM endpoint is contacted.

Exit-code contract under test:
  0 ok / 1 business error / 2 transport / 3 no key / 4 arg validation.
"""

from __future__ import annotations

import json
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


class _FakeClient:
    """Stand-in for ``LKMClient`` capturing the last request."""

    last_call: ClassVar[dict[str, Any]] = {}

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
        return _FakeClient(response=response, raises=raises)

    monkeypatch.setattr(_shared, "LKMClient", factory)
    _FakeClient.last_call = {}


def _install_constructor_error(monkeypatch: pytest.MonkeyPatch, raises: Exception) -> None:
    """Patch ``_shared.LKMClient`` to fail during construction."""

    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        raise raises

    monkeypatch.setattr(_shared, "LKMClient", factory)
    _FakeClient.last_call = {}


# --------------------------------------------------------------------------- #
# knowledge                                                                   #
# --------------------------------------------------------------------------- #


class TestKnowledge:
    def test_happy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(app, ["search", "lkm", "knowledge", "perovskite"])
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["query"] == "perovskite"
        assert body["retrieval_mode"] == "hybrid"
        assert body["filters"] == {"visibility": "public"}

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
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "n": 1})
        dest = tmp_path / "nested" / "out.json"
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "q", "--format", "raw-json", "--out", str(dest)],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(dest.read_text())["code"] == 0

    def test_claims_alias_still_dispatches_to_search_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(app, ["search", "lkm", "claims", "perovskite"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["path"] == "/search"

    def test_default_normalizes_knowledge_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "papers": {
                        "paper:811827932371615744": {
                            "doi": "10.1016/j.jpcs.2021.110374",
                            "en_title": "FAPbI3 processing paper",
                            "id": "811827932371615744",
                        }
                    },
                    "variables": [
                        {
                            "content": "Annealing at 120 C maximizes alpha phase.",
                            "has_evidence": True,
                            "has_reasoning": True,
                            "id": "gcn_579430355a0e4bbd",
                            "provenance": {
                                "representative_lcn": {
                                    "local_id": "paper:811827932371615744::conclusion_4",
                                    "package_id": "paper:811827932371615744",
                                    "version": "2.0.0",
                                },
                                "source_packages": ["paper:811827932371615744"],
                            },
                            "role": "conclusion",
                            "score": 0.97,
                            "title": "Annealing temperature controls alpha-phase growth",
                            "type": "claim",
                        }
                    ],
                },
            },
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "FAPbI3"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["schema_version"] == 1
        assert out["query"] == {"text": "FAPbI3", "provider": "lkm", "kind": "knowledge"}
        item = out["results"][0]
        assert item["id"] == "lkm:gcn_579430355a0e4bbd"
        assert item["kind"] == "claim"
        assert item["rank"] == {"score": 0.97, "score_kind": "retrieval"}
        assert item["gaia"]["object_kind"] == "claim"
        assert item["source"]["paper_id"] == "811827932371615744"
        assert item["source"]["doi"] == "10.1016/j.jpcs.2021.110374"
        assert item["actions"] == [
            {
                "kind": "inspect",
                "command": "gaia search lkm reasoning gcn_579430355a0e4bbd",
            },
            {
                "kind": "add",
                "ref": "lkm:paper:811827932371615744",
                "command": "gaia pkg add lkm:paper:811827932371615744",
            },
        ]

    def test_gaia_json_omits_inspect_when_claim_has_no_reasoning(
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
        item = json.loads(result.output)["results"][0]
        assert item["actions"] == []

    def test_gaia_json_maps_question_variables_to_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "variables": [
                        {
                            "content": "Which phase conversion pathway dominates?",
                            "id": "gq_123",
                            "provenance": {
                                "source_packages": ["paper:811827932371615744"],
                            },
                            "title": "Phase conversion question",
                            "type": "question",
                        }
                    ],
                },
            },
        )

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "phase conversion",
                "--scopes",
                "question",
                "--format",
                "gaia-json",
            ],
        )

        assert result.exit_code == 0, result.output
        item = json.loads(result.output)["results"][0]
        assert json.loads(result.output)["query"]["kind"] == "question"
        assert item["kind"] == "question"
        assert item["gaia"]["object_kind"] == "question"

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
        assert json.loads(result.output)["query"] == {
            "text": "open problem",
            "provider": "lkm",
            "kind": "question",
        }

    def test_gaia_json_maps_unknown_variable_types_to_note(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "variables": [
                        {
                            "content": "Provider-specific context node.",
                            "id": "gctx_123",
                            "title": "Provider context",
                            "type": "provider_context",
                        }
                    ],
                },
            },
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "context", "--format", "gaia-json"],
        )

        assert result.exit_code == 0, result.output
        item = json.loads(result.output)["results"][0]
        assert item["kind"] == "note"
        assert item["gaia"]["object_kind"] == "note"


# --------------------------------------------------------------------------- #
# reasoning                                                                   #
# --------------------------------------------------------------------------- #


class TestReasoning:
    def test_happy_top_level_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={"code": 0, "msg": "ok", "reasoning_chains": [], "total_chains": 0},
        )
        result = runner.invoke(app, ["search", "lkm", "reasoning", "gcn_abc123"])
        assert result.exit_code == 0, result.output
        call = _FakeClient.last_call
        assert call["method"] == "GET"
        assert call["path"] == "/claims/gcn_abc123/reasoning"
        assert call["params"] == {"max_chains": 10, "sort_by": "comprehensive"}

    def test_url_encodes_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok"})
        result = runner.invoke(app, ["search", "lkm", "reasoning", "a/b c"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["path"] == "/claims/a%2Fb%20c/reasoning"

    def test_data_nested_shape_flattened(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "msg": "ok",
                "data": {"reasoning_chains": [{"id": 1}], "total_chains": 1},
            },
        )
        result = runner.invoke(app, ["search", "lkm", "reasoning", "x"])
        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["reasoning_chains"] == [{"id": 1}]
        assert out["total_chains"] == 1

    def test_max_chains_out_of_range_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "reasoning", "x", "--max-chains", "101"])
        assert result.exit_code == 4, result.output

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290004, "msg": "claim not found"})
        result = runner.invoke(app, ["search", "lkm", "reasoning", "x"])
        assert result.exit_code == 1, result.output


# --------------------------------------------------------------------------- #
# reasoning-search                                                            #
# --------------------------------------------------------------------------- #


class TestReasoningSearch:
    def test_happy_plural_paper_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning-search",
                "q",
                "--paper-ids",
                "123",
                "--paper-ids",
                "456",
            ],
        )
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["filters"] == {"paper_ids": ["123", "456"]}

    def test_rejects_paper_prefix_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning-search", "q", "--paper-ids", "paper:123"],
        )
        assert result.exit_code == 4, result.output
        assert "paper:" in result.output

    def test_too_many_keywords_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        args = ["search", "lkm", "reasoning-search", "q"]
        for i in range(11):
            args += ["--keywords", f"k{i}"]
        result = runner.invoke(app, args)
        assert result.exit_code == 4, result.output

    def test_limit_out_of_range_exits_4_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "reasoning-search", "q", "--limit", "101"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_offset_out_of_range_exits_4_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "reasoning-search", "q", "--offset", "-1"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_transport_error_exits_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=LKMTransportError("net"))
        result = runner.invoke(app, ["search", "lkm", "reasoning-search", "q"])
        assert result.exit_code == 2, result.output

    def test_default_normalizes_reasoning_chain_results(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
                "code": 0,
                "data": {
                    "papers": {
                        "paper:811827932371615744": {
                            "doi": "10.1016/j.jpcs.2021.110374",
                            "id": "811827932371615744",
                        }
                    },
                    "reasoning_chains": [
                        {
                            "id": "chain_1",
                            "source_package": "paper:811827932371615744",
                            "factors": [
                                {
                                    "conclusion": {
                                        "content": "120 C is the optimal annealing window.",
                                        "id": "gcn_result",
                                        "title": "Optimal annealing window",
                                    },
                                    "steps": [{"reasoning": "Compare 120 C and 150 C."}],
                                }
                            ],
                        }
                    ],
                },
            },
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning-search", "FAPbI3"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["query"] == {"text": "FAPbI3", "provider": "lkm", "kind": "derive"}
        item = out["results"][0]
        assert item["id"] == "lkm:chain_1"
        assert item["kind"] == "derive"
        assert item["gaia"]["object_kind"] == "derive"
        assert item["title"] == "Optimal annealing window"
        assert item["content"] == "120 C is the optimal annealing window."
        assert item["source"]["paper_id"] == "811827932371615744"
        assert item["actions"] == [
            {
                "kind": "add",
                "ref": "lkm:paper:811827932371615744",
                "command": "gaia pkg add lkm:paper:811827932371615744",
            }
        ]


# --------------------------------------------------------------------------- #
# variables                                                                   #
# --------------------------------------------------------------------------- #


class TestVariables:
    def test_happy_dedupe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "variables", "a", "b", "a"])
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a", "b"]}

    def test_merge_with_ids_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _install_client(monkeypatch)
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("b\nc\n\n", encoding="utf-8")
        result = runner.invoke(
            app, ["search", "lkm", "variables", "a", "b", "--ids-file", str(ids_file)]
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {"ids": ["a", "b", "c"]}

    def test_empty_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "variables"])
        assert result.exit_code == 4, result.output

    def test_missing_ids_file_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app, ["search", "lkm", "variables", "a", "--ids-file", "/nonexistent/x.txt"]
        )
        assert result.exit_code == 4, result.output

    def test_no_key_exits_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=NoAccessKeyError("no key"))
        result = runner.invoke(app, ["search", "lkm", "variables", "a"])
        assert result.exit_code == 3, result.output


# --------------------------------------------------------------------------- #
# paper-graph                                                                 #
# --------------------------------------------------------------------------- #


class TestPaperGraph:
    def test_happy_default_include(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "paper-graph", "--paper-id", "p1"])
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["paper_id"] == "p1"
        assert body["include"] == ["paper", "variables", "factors", "motivations"]

    def test_no_identifier_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "paper-graph"])
        assert result.exit_code == 4, result.output

    def test_two_identifiers_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app, ["search", "lkm", "paper-graph", "--paper-id", "p1", "--doi", "d1"]
        )
        assert result.exit_code == 4, result.output

    def test_include_and_no_hydrate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "paper-graph",
                "--package-id",
                "paper:1",
                "--include",
                "priors",
                "--include",
                "factor_params",
                "--no-hydrate-factor-refs",
            ],
        )
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["package_id"] == "paper:1"
        assert body["include"] == ["priors", "factor_params"]
        assert body["hydrate_factor_refs"] is False

    def test_title_resolve_limit_with_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "paper-graph", "--title", "t", "--title-resolve-limit", "7"],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["title_resolve"] == {"limit": 7}

    def test_title_resolve_limit_without_title_exits_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "paper-graph", "--paper-id", "p1", "--title-resolve-limit", "7"],
        )
        assert result.exit_code == 4, result.output

    def test_title_resolve_limit_out_of_range_exits_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "paper-graph", "--title", "t", "--title-resolve-limit", "21"],
        )
        assert result.exit_code == 4, result.output

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290011, "msg": "not found"})
        result = runner.invoke(app, ["search", "lkm", "paper-graph", "--doi", "d"])
        assert result.exit_code == 1, result.output

    def test_default_normalizes_paper_graph_as_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
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
                                "motivations_total": 1,
                                "variables_total": 25,
                            },
                        }
                    ]
                },
            },
        )

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "paper-graph",
                "--paper-id",
                "811827932371615744",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["query"] == {
            "text": "811827932371615744",
            "provider": "lkm",
            "kind": "package",
        }
        item = out["results"][0]
        assert item["id"] == "lkm:paper:811827932371615744"
        assert item["kind"] == "package"
        assert item["gaia"]["object_kind"] == "package"
        assert item["title"] == "Controlling phase and morphology"
        assert item["source"]["source_package"] == "paper:811827932371615744"
        assert item["source"]["stats"]["variables_total"] == 25
        assert item["actions"] == [
            {
                "kind": "add",
                "ref": "lkm:paper:811827932371615744",
                "command": "gaia pkg add lkm:paper:811827932371615744",
            }
        ]

    def test_gaia_json_does_not_invent_add_ref_without_paper_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(
            monkeypatch,
            response={
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
            },
        )

        result = runner.invoke(
            app,
            ["search", "lkm", "paper-graph", "--title", "ambiguous candidate"],
        )

        assert result.exit_code == 0, result.output
        item = json.loads(result.output)["results"][0]
        assert item["id"] == "lkm:paper-graph:0"
        assert item["source"]["paper_id"] is None
        assert item["source"]["source_package"] is None
        assert item["actions"] == []
