"""Tests for the public ``gaia search lkm`` verbs.

Every HTTP call is mocked by replacing ``_lkm_runtime.LKMClient`` with a fake
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

from gaia.cli import _lkm_runtime
from gaia.cli._credentials import CredentialPermissionError
from gaia.cli.commands.search.lkm._client import (
    LKMNotFoundError,
    LKMPermissionError,
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.cli.commands.search.lkm.policy import build_lkm_filters
from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _squash_ws(text: str) -> str:
    return " ".join(_strip_ansi(text).split())


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
    """Patch ``_lkm_runtime.LKMClient`` so verbs use the fake (no key required)."""

    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        if raises is not None and isinstance(raises, NoAccessKeyError):
            raise raises
        _FakeClient.last_init_kwargs = dict(_kwargs)
        return _FakeClient(response=response, raises=raises)

    monkeypatch.setattr(_lkm_runtime, "LKMClient", factory)
    _FakeClient.last_call = {}
    _FakeClient.last_init_kwargs = {}


def _install_constructor_error(monkeypatch: pytest.MonkeyPatch, raises: Exception) -> None:
    """Patch ``_lkm_runtime.LKMClient`` to fail during construction."""

    def factory(*_args: object, **_kwargs: object) -> _FakeClient:
        raise raises

    monkeypatch.setattr(_lkm_runtime, "LKMClient", factory)
    _FakeClient.last_call = {}


# --------------------------------------------------------------------------- #
# docs                                                                        #
# --------------------------------------------------------------------------- #


class TestDocs:
    def test_lkm_help_uses_armchair_lkm_framing(self) -> None:
        result = runner.invoke(app, ["search", "lkm", "--help"])

        assert result.exit_code == 0, result.output
        stdout = _squash_ws(result.stdout)
        assert "paper knowledge items" in stdout
        assert "weak-point / highlight claims" in stdout
        assert "problems" in stdout
        assert "open questions" in stdout
        assert "reasoning chains and workflows" in stdout
        assert "bibliographic forward references" in stdout
        assert "generic graph API" in stdout
        assert "knowledge graph" not in stdout
        assert "claim/question records" not in stdout
        assert "workflow-shaped evidence" not in stdout

    def test_prints_lkm_api_and_cli_reference_links(self) -> None:
        result = runner.invoke(app, ["search", "lkm", "docs"])

        assert result.exit_code == 0, result.output
        assert "LKM API docs:" in result.stdout
        assert "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84" in result.stdout
        assert "knowledge search" in result.stdout
        assert "reasoning search" in result.stdout
        assert "claim reasoning lookup" in result.stdout
        assert "node lookup" in result.stdout
        assert "paper graph lookup" in result.stdout
        assert "paper reference lookup" in result.stdout
        assert "feedback" in result.stdout
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
            (
                ["search", "lkm", "references", "--help"],
                ["POST /papers/reference"],
            ),
            (
                ["search", "lkm", "feedback", "--help"],
                ["https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-474487249"],
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


class TestPolicy:
    def test_filter_policy_preserves_gaia_defaults_without_spurious_server_defaults(
        self,
    ) -> None:
        assert build_lkm_filters(
            visibility="public",
            role=None,
            paper_ids=None,
            dois=None,
            title=None,
            publication_date_start=None,
            publication_date_end=None,
            limit_publication_date=True,
        ) == {"visibility": "public"}

    def test_filter_policy_includes_new_lkm_filters_when_explicit(self) -> None:
        assert build_lkm_filters(
            visibility=None,
            role="conclusion",
            paper_ids=["123"],
            dois=["10.1038/example"],
            title="phase stability",
            publication_date_start="2020-01-01",
            publication_date_end="2024-12-31",
            limit_publication_date=False,
        ) == {
            "role": "conclusion",
            "paper_ids": ["123"],
            "dois": ["10.1038/example"],
            "title": "phase stability",
            "publication_date_start": "2020-01-01",
            "publication_date_end": "2024-12-31",
            "limit_publication_date": False,
        }


class TestKnowledge:
    def test_help_recommends_reasoning_only_for_conclusions(self) -> None:
        result = runner.invoke(app, ["search", "lkm", "knowledge", "--help"])

        assert result.exit_code == 0, result.output
        stdout = _squash_ws(result.stdout)
        assert "--reasoning-only" in stdout
        assert "conclusions" in stdout
        assert "paper knowledge items" in stdout
        assert "weak-point / highlight claims" in stdout
        assert "open questions" in stdout
        assert "reasoning chains and workflows" in stdout
        assert "premise" in stdout
        assert "open_question" in stdout
        assert "reasoning_chain" in stdout
        assert "claim/question records" not in stdout
        assert "workflow-shaped evidence" not in stdout

    def test_happy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "msg": "ok", "variables": []})
        result = runner.invoke(app, ["search", "lkm", "knowledge", "perovskite"])
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["query"] == "perovskite"
        assert body["retrieval_mode"] == "hybrid"
        assert body["sort_by"] == "comprehensive"
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
        assert "Suggested: inspect the supporting reasoning graph" in result.stderr
        assert "gaia search lkm reasoning --index bohrium --claim-id gcn_579430355a0e4bbd" in (
            result.stderr
        )
        assert "Suggested: materialize the source paper as a Gaia package" in result.stderr
        assert "editable local dependency under .gaia/lkm_packages/" in result.stderr
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

    def test_search_update_options_build_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "battery",
                "--sort-by",
                "recent",
                "--paper-ids",
                "123",
                "--paper-ids",
                "456",
                "--doi",
                "10.1038/example",
                "--title",
                "phase stability",
                "--publication-date-start",
                "2020-01-01",
                "--publication-date-end",
                "2024-12-31",
                "--no-limit-publication-date",
                "--visibility",
                "private",
            ],
        )

        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["sort_by"] == "recent"
        assert body["filters"] == {
            "visibility": "private",
            "paper_ids": ["123", "456"],
            "dois": ["10.1038/example"],
            "title": "phase stability",
            "publication_date_start": "2020-01-01",
            "publication_date_end": "2024-12-31",
            "limit_publication_date": False,
        }

    def test_rejects_prefixed_paper_ids_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "knowledge", "q", "--paper-ids", "paper:123"],
        )
        assert result.exit_code == 4, result.output
        assert "without the `paper:` prefix" in result.output
        assert _FakeClient.last_call == {}

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

    def test_allows_all_search_scopes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        scopes = [
            "abstract",
            "claim",
            "premise",
            "conclusion",
            "question",
            "problem",
            "open_question",
            "subproblem",
            "reasoning_chain",
        ]
        args = ["search", "lkm", "knowledge", "paper knowledge"]
        for scope in scopes:
            args.extend(["--scopes", scope])
        result = runner.invoke(
            app,
            args,
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["scopes"] == scopes

    @pytest.mark.parametrize("question_role", ["problem", "open_question", "subproblem"])
    def test_question_roles_round_trip_in_raw_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        question_role: str,
    ) -> None:
        payload = {
            "code": 0,
            "data": {
                "variables": [
                    {
                        "id": "gcn_question",
                        "type": "question",
                        "role": question_role,
                        "content": "What remains unresolved?",
                    }
                ]
            },
        }
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "knowledge",
                "unresolved mechanisms",
                "--scopes",
                question_role,
                "--no-hint",
            ],
        )

        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["scopes"] == [question_role]
        assert json.loads(result.stdout) == payload

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

    def test_rejects_reasoning_only_with_conclusion_scope(
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
                "conclusion",
                "--reasoning-only",
            ],
        )
        assert result.exit_code == 4, result.output
        assert "Use `--scopes conclusion` without --reasoning-only" in result.output
        assert _FakeClient.last_call == {}

    def test_rejects_reasoning_only_with_non_conclusion_role(
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
                "--reasoning-only",
                "--role",
                "highlight",
            ],
        )
        assert result.exit_code == 4, result.output
        assert "--reasoning-only requires --role to be omitted or `conclusion`" in result.output
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

    def test_permission_error_exits_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=LKMPermissionError("denied"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 2, result.output
        assert "denied" in result.output

    def test_not_found_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=LKMNotFoundError("missing"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 1, result.output
        assert "missing" in result.output

    def test_no_key_exits_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, raises=NoAccessKeyError("no key"))
        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])
        assert result.exit_code == 3, result.output

    @pytest.mark.parametrize(
        ("retry_error", "expected_exit", "expected_text"),
        [
            (LKMPermissionError("denied after onboarding"), 2, "denied after onboarding"),
            (LKMNotFoundError("missing after onboarding"), 1, "missing after onboarding"),
        ],
    )
    def test_retry_after_onboarding_maps_typed_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        retry_error: Exception,
        expected_exit: int,
        expected_text: str,
    ) -> None:
        attempts = 0

        class RetryClient:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise NoAccessKeyError("no key")

            def __enter__(self) -> RetryClient:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
                raise retry_error

        monkeypatch.setattr(_lkm_runtime, "LKMClient", RetryClient)
        monkeypatch.setattr(_lkm_runtime, "try_interactive_onboarding", lambda **_kwargs: True)

        result = runner.invoke(app, ["search", "lkm", "knowledge", "q"])

        assert result.exit_code == expected_exit, result.output
        assert expected_text in result.output

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

    def test_query_search_accepts_search_update_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "thermal stability",
                "--sort-by",
                "journal",
                "--paper-ids",
                "123",
                "--doi",
                "10.1038/example",
                "--title",
                "phase stability",
                "--publication-date-start",
                "2020-01-01",
                "--publication-date-end",
                "2024-12-31",
                "--no-limit-publication-date",
            ],
        )

        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["sort_by"] == "journal"
        assert body["filters"] == {
            "paper_ids": ["123"],
            "dois": ["10.1038/example"],
            "title": "phase stability",
            "publication_date_start": "2020-01-01",
            "publication_date_end": "2024-12-31",
            "limit_publication_date": False,
        }

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

    def test_rejects_new_query_filters_in_claim_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "reasoning",
                "--claim-id",
                "gcn_abc123",
                "--title",
                "phase stability",
            ],
        )
        assert result.exit_code == 4, result.output
        assert "--title" in result.output
        assert _FakeClient.last_call == {}

    def test_rejects_query_only_sort_values_in_claim_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "reasoning", "--claim-id", "gcn_abc123", "--sort-by", "journal"],
        )
        assert result.exit_code == 4, result.output
        assert "comprehensive or recent" in result.output
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
        assert "Suggested: materialize the source paper as a Gaia package" in result.stderr
        assert "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744" in (result.stderr)

    def test_claim_reasoning_without_paper_hints_claim_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {"code": 0, "data": {"reasoning_chains": []}}
        _install_client(monkeypatch, response=payload)

        result = runner.invoke(app, ["search", "lkm", "reasoning", "--claim-id", "gcn_result"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert "Suggested: resolve this claim to its source paper" in result.stderr
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
        assert "Suggested: materialize the source paper as a Gaia package" in result.stderr
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
# feedback                                                                    #
# --------------------------------------------------------------------------- #


class TestFeedback:
    def test_posts_feedback_with_gcn_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 0, "data": {"id": "fb_1"}})

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "feedback",
                "--type",
                "bug",
                "--gcn-id",
                "gcn_abc",
                "Missing premise nodes.",
            ],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {"code": 0, "data": {"id": "fb_1"}}
        assert _FakeClient.last_call == {
            "method": "POST",
            "path": "/feedback",
            "json_body": {
                "type": "bug",
                "content": "Missing premise nodes.",
                "gcn_id": "gcn_abc",
            },
            "params": None,
        }

    def test_posts_feedback_with_paper_metadata_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "feedback",
                "--type",
                "feature",
                "--paper-metadata-id",
                "867766664756724177",
                "Please expose better paper metadata.",
            ],
        )

        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {
            "type": "feature",
            "content": "Please expose better paper metadata.",
            "paper_metadata_id": "867766664756724177",
        }

    def test_rejects_both_feedback_targets_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)

        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "feedback",
                "--type",
                "question",
                "--gcn-id",
                "gcn_abc",
                "--paper-metadata-id",
                "867766664756724177",
                "Which paper is this linked to?",
            ],
        )

        assert result.exit_code == 4, result.output
        assert "mutually exclusive" in result.output
        assert _FakeClient.last_call == {}

    def test_rejects_blank_feedback_content_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_client(monkeypatch)

        result = runner.invoke(app, ["search", "lkm", "feedback", "--type", "bug", "   "])

        assert result.exit_code == 4, result.output
        assert "content" in result.output
        assert _FakeClient.last_call == {}


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
        assert "Suggested: materialize this paper as a Gaia package" in result.stderr
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


# --------------------------------------------------------------------------- #
# references                                                                  #
# --------------------------------------------------------------------------- #


_REFERENCE_SEED_ID = "1020661015349559308"
_REFERENCE_NEIGHBOR_ID = "811827932371615744"


def _reference_payload(*, seed_id: str = _REFERENCE_SEED_ID) -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "papers": [
                {
                    "id": seed_id,
                    "doi": "10.1093/nar/gkae620",
                    "en_title": "Example seed paper",
                    "references": None,
                    "cited_by": [
                        {
                            "id": _REFERENCE_NEIGHBOR_ID,
                            "doi": "10.1016/j.jpcs.2021.110374",
                            "en_title": "Citing paper",
                        }
                    ],
                }
            ]
        },
    }


class TestReferences:
    def test_happy_default_posts_reference_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app, ["search", "lkm", "references", "--paper-id", _REFERENCE_SEED_ID]
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["method"] == "POST"
        assert _FakeClient.last_call["path"] == "/papers/reference"
        assert _FakeClient.last_call["json_body"] == {
            "paper_ids": [_REFERENCE_SEED_ID],
            "with_abstract": True,
            "with_reference": False,
            "with_cited_by": True,
        }

    def test_accepts_doi_and_repeatable_seeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "references",
                "--paper-id",
                _REFERENCE_SEED_ID,
                "--doi",
                "10.1038/s41586-021-03381-x",
                "--doi",
                "10.1093/nar/gkae620",
            ],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"] == {
            "paper_ids": [_REFERENCE_SEED_ID],
            "dois": ["10.1038/s41586-021-03381-x", "10.1093/nar/gkae620"],
            "with_abstract": True,
            "with_reference": False,
            "with_cited_by": True,
        }

    def test_include_flags_are_sent_explicitly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "references",
                "--paper-id",
                _REFERENCE_SEED_ID,
                "--no-with-abstract",
                "--with-reference",
                "--no-with-cited-by",
            ],
        )
        assert result.exit_code == 0, result.output
        body = _FakeClient.last_call["json_body"]
        assert body["with_abstract"] is False
        assert body["with_reference"] is True
        assert body["with_cited_by"] is False

    def test_strips_paper_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "references", "--paper-id", f"paper:{_REFERENCE_SEED_ID}"],
        )
        assert result.exit_code == 0, result.output
        assert _FakeClient.last_call["json_body"]["paper_ids"] == [_REFERENCE_SEED_ID]

    def test_no_identifier_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "references"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_empty_doi_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "references", "--doi", "   "])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_empty_paper_prefix_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "references", "--paper-id", "paper:"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_non_numeric_paper_id_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(app, ["search", "lkm", "references", "--paper-id", "p1"])
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_too_many_seeds_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        args = ["search", "lkm", "references"]
        for i in range(21):
            args.extend(["--paper-id", str(1000 + i)])
        result = runner.invoke(app, args)
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_combined_seed_cap_counts_both_sides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        args = ["search", "lkm", "references"]
        for i in range(10):
            args.extend(["--paper-id", str(1000 + i)])
        for i in range(11):
            args.extend(["--doi", f"10.0.0/{i}"])
        result = runner.invoke(app, args)
        assert result.exit_code == 4, result.output
        assert _FakeClient.last_call == {}

    def test_unknown_title_flag_exits_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch)
        result = runner.invoke(
            app,
            ["search", "lkm", "references", "--paper-id", _REFERENCE_SEED_ID, "--title", "x"],
        )
        assert result.exit_code == 2, result.output
        assert _FakeClient.last_call == {}

    def test_business_error_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_client(monkeypatch, response={"code": 290002, "msg": "too many seeds"})
        result = runner.invoke(
            app, ["search", "lkm", "references", "--paper-id", _REFERENCE_SEED_ID]
        )
        assert result.exit_code == 1, result.output

    def test_default_emits_raw_papers_with_package_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = _reference_payload()
        _install_client(monkeypatch, response=payload)
        result = runner.invoke(
            app, ["search", "lkm", "references", "--paper-id", _REFERENCE_SEED_ID]
        )
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.stdout)
        assert parsed == payload
        assert "items" not in parsed.get("data", {})
        assert parsed["data"]["papers"][0]["id"] == _REFERENCE_SEED_ID
        assert (
            f"gaia search lkm package --index bohrium --paper-id {_REFERENCE_SEED_ID}"
            in result.stderr
        )
        assert "gaia pkg add" not in result.stderr

    def test_doi_only_uncovered_paper_has_no_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "code": 0,
            "data": {
                "papers": [
                    {
                        "id": "",
                        "doi": "10.1038/s41586-021-03381-x",
                        "en_title": "Uncovered seed",
                        "references": None,
                        "cited_by": [],
                    }
                ]
            },
        }
        _install_client(monkeypatch, response=payload)
        result = runner.invoke(
            app,
            ["search", "lkm", "references", "--doi", "10.1038/s41586-021-03381-x"],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_doi_only_covered_paper_hints_package(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = _reference_payload()
        _install_client(monkeypatch, response=payload)
        result = runner.invoke(
            app,
            ["search", "lkm", "references", "--doi", "10.1093/nar/gkae620"],
        )
        assert result.exit_code == 0, result.output
        assert (
            f"gaia search lkm package --index bohrium --paper-id {_REFERENCE_SEED_ID}"
            in result.stderr
        )

    def test_no_hint_suppresses_package_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = _reference_payload()
        _install_client(monkeypatch, response=payload)
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "references",
                "--paper-id",
                _REFERENCE_SEED_ID,
                "--no-hint",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == payload
        assert result.stderr == ""

    def test_out_writes_raw_file_and_hint_to_stderr(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        payload = _reference_payload()
        _install_client(monkeypatch, response=payload)
        dest = tmp_path / "nested" / "papers_reference.json"
        result = runner.invoke(
            app,
            [
                "search",
                "lkm",
                "references",
                "--paper-id",
                _REFERENCE_SEED_ID,
                "--out",
                str(dest),
            ],
        )
        assert result.exit_code == 0, result.output
        assert result.stdout == ""
        assert json.loads(dest.read_text()) == payload
        assert (
            f"gaia search lkm package --index bohrium --paper-id {_REFERENCE_SEED_ID}"
            in result.stderr
        )
