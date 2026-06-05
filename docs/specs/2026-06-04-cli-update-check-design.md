# `gaia` CLI PyPI update-check + upgrade notice

> **Status:** Draft
>
> **Date:** 2026-06-04
>
> **Scope:** `gaia/cli/` — a non-blocking PyPI update check surfaced on CLI
> invocation.
>
> **Non-goals:** auto-running upgrades, granular CLI-vs-library channels,
> telemetry beyond the anonymous PyPI JSON GET, a stable-only mode.

## 1. Context & decision

`gaia-lang` ships the CLI and the importable library as **one wheel**
(`[project.scripts] gaia = "gaia.cli.main:app"`, plus the importable `gaia`
package). We considered splitting into independently-versioned distributions
for granular CLI-vs-library upgrades and **rejected it**: too much surface
(workspace, namespace split, dual release pipeline, back-compat).

**Decision:** keep one package, upgrade the whole of `gaia` as a unit. Add a
lightweight, non-blocking **update check** to the CLI: on invocation, check
PyPI (including prereleases — the published line is the `0.5.0aN` alpha) for a
newer `gaia-lang`; if one exists, print a notice prompting the user/agent to
upgrade. No granular channels, no auto-running the upgrade.

## 2. Goals

- On `gaia` invocation, detect when a newer `gaia-lang` exists on PyPI
  (prereleases included) and surface a one-line upgrade notice.
- Zero impact on automation: never block, never hang, never fail a command
  because of the check.
- Cheap: at most one network call per day, cached.

## 3. Behavior

1. **Hook point:** the root `@app.callback()` in `gaia/cli/main.py` (runs
   before every command). The check runs there, after the eager `--version`
   short-circuit, and is skipped for the bare-help / no-args case
   (`ctx.invoked_subcommand is None`), guarded by all the skip conditions
   below.
2. **What it does:** resolves the latest `gaia-lang` version on PyPI
   **including prereleases**; if `latest > installed` (PEP 440 ordering),
   prints a notice to **stderr**:

   ```
   gaia-lang 0.5.0a4 is available (you have 0.5.0a1).
   Upgrade:  <install-method-specific command>
   (silence: GAIA_NO_UPDATE_CHECK=1)
   ```

3. **Non-blocking / agent-safe (mandatory):**
   - Output goes to **stderr only** — never stdout (keeps machine-parsed
     stdout clean).
   - **Never reads stdin** — it is a notice, not an interactive prompt (an
     agent would hang on a prompt).
   - Network call has a **short, per-phase timeout** (connect 0.75s, read 1.5s
     via `httpx.Timeout(1.5, connect=0.75)` — bounds, not a single total
     deadline) and **fails silent** — any `httpx.HTTPError`, timeout, non-200,
     malformed JSON, or offline state → no output, no error, command proceeds
     normally.
   - Cheap path first: if the daily cache says "checked recently", skip the
     network entirely and reuse the cached result.
4. **Throttle (≤ once/day):** cache stamp under the XDG cache dir; only hit
   PyPI if the stamp is older than the TTL (default 24h). The stamp is
   rewritten after every *attempt* (success or failure) so a flaky network
   can't cause a per-invocation retry storm.
5. **Opt-out / skip conditions** (any one suppresses the check entirely,
   before any network):
   - `GAIA_NO_UPDATE_CHECK=1` (or truthy) in env.
   - `CI` env var set (skip in CI by default).
   - The invocation is `gaia --version` (eager callback already exits) or
     `gaia` with no args / bare help (no subcommand to run).
   - Installed version cannot be resolved (e.g. running from a source
     checkout where the dist isn't installed) → skip silently.
   - `stderr` is not writable / closed → skip.

## 4. Implementation

- **New module:** `gaia/cli/_update_check.py`. The `main.py` call site is a
  single `maybe_notify_update()` guarded by a broad `try/except Exception:
  pass` so the feature can never break the CLI.
- **Installed version:** reuse `get_library_version()` (`gaia/_meta.py` →
  `importlib.metadata.version("gaia-lang")`).
- **PyPI query:** `httpx.get("https://pypi.org/pypi/gaia-lang/json",
  timeout=httpx.Timeout(1.5, connect=0.75))` (httpx is already a dep; mirrors
  the `_registry.py` pattern: `try/except httpx.HTTPError`). The timeout is
  per-phase (connect 0.75s, read 1.5s), not a single total deadline. Parses **all keys of `releases`** (not
  `info.version`, which is the latest *stable* and would miss the alpha line);
  skips fully-yanked releases; takes the max via PEP 440 ordering.
- **Version comparison:** `packaging.version.Version`. `packaging` is declared
  in `[project].dependencies` (`packaging>=23`) so it is guaranteed at
  runtime — previously it was only a transitive dev dep. PEP 440 prerelease
  ordering is never hand-rolled.
- **Cache:** JSON file `{"checked_at": <epoch>, "latest": "<version>"}` at
  `$XDG_CACHE_HOME/gaia/update-check.json` (fallback
  `~/.cache/gaia/update-check.json`) — XDG-aware (cache → `XDG_CACHE_HOME`,
  not config; cf. `_credentials.py`'s `XDG_CONFIG_HOME`). Created with
  `parents=True, exist_ok=True`; written atomically (mirrors
  `_credentials._atomic_write`); TTL default 24h, overridable via
  `GAIA_UPDATE_CHECK_TTL` (seconds) for tests.
- **Install-method detection** (best-effort → tailors the upgrade command;
  generic fallback if unsure):
  - executable / prefix under a `uv/tools/…` layout →
    `uv tool upgrade --prerelease=allow gaia-lang`.
  - inside a `.venv` with a sibling `pyproject.toml`/`uv.lock` →
    `uv add --prerelease=allow gaia-lang@latest`.
  - other virtualenv → `pip install -U --pre gaia-lang`.
  - **fallback (unsure):** shows the `pip install -U --pre gaia-lang` form
    plus the `uv tool upgrade` form.
  - All shown commands allow prereleases (`--pre` / `--prerelease=allow`) to
    match the alpha channel.

## 5. Edge cases / failure modes

| Situation | Behavior |
|---|---|
| Offline / DNS fail / timeout | silent skip; stamp rewritten to throttle |
| PyPI 5xx / non-200 | silent skip; stamp rewritten |
| Malformed / unexpected JSON | silent skip; stamp rewritten |
| Cache dir unwritable | attempt network; write swallowed; never error |
| Installed == latest | no output |
| Installed > latest (dev/local build ahead) | no output |
| Running from un-installed source checkout | version unresolved → skip |
| `GAIA_NO_UPDATE_CHECK` / `CI` set | skip before network |

## 6. Testing (must not touch the network)

- Inject a fetcher (or monkeypatch the default fetcher) — assert the notice
  fires when latest > installed, including a **prerelease > prerelease** case
  (`0.5.0a1` → `0.5.0a4`) and stable-vs-pre ordering.
- Assert **silence** when: equal, installed ahead, opt-out env set, `CI` set,
  network raises, JSON malformed, version unresolved, stderr closed.
- Assert **throttle**: a second call within the TTL makes no network call
  (stamp honored); a call after the TTL does.
- Assert the notice goes to **stderr**, stdout is untouched, and stdin is
  never read.
- Use a tmp `XDG_CACHE_HOME` fixture; honor `GAIA_UPDATE_CHECK_TTL`. Marked
  `pr_gate`; fast (no real I/O).

## 7. Out-of-scope follow-ups (note, don't build)

- A `gaia self upgrade` command that actually runs the detected upgrade.
- An opt-in config setting (vs env var) once/if a real config system lands.
