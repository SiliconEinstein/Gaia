"""Exploration map state — the fog-of-war "save-game" overlay.

This module owns the durable artifact of gaia exploration:
``.gaia/exploration/map.json`` plus an append-only round log at
``.gaia/exploration/rounds.jsonl``. It is a NEW sibling to ``.gaia/inquiry/``
and mirrors that module's proven patterns (versioned dataclasses with
``to_dict`` / ``from_dict``, a dir helper keyed off ``pkg_path``, atomic
``tmp.replace(path)`` writes, a version gate that refuses a newer on-disk
version, an append-only jsonl log, and a ``mint_*`` id helper).

Per SCHEMA.md §0, this artifact is an **index/overlay** over the IR: it points
into the IR by QID and adds only what the IR does not carry (exploration
provenance, frontier, policy, round history). It never duplicates node content
and — like ``inquiry/state.py`` — never touches ``.py`` source / IR / priors /
``beliefs.json``. Node content, type, provenance, and belief are read from the
IR / ``beliefs.json`` by QID, never copied here.

The dataclasses mirror SCHEMA.md §2 through §7:
  - ExplorationMap  — top-level versioned overlay (§2)
  - SurveyRecord    — overlay on a materialized IR node (§3a)
  - Contact         — a referenced-but-unexpanded frontier target (§3b)
  - Policy          — the per-round exploration dial (§4)

Fog is not stored: it is the implicit complement of the surveyed and frontier
sets.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPLORATION_SCHEMA_VERSION = 1

# §3b — the back-ref edge kinds a surveyed node can reach a contact through.
VALID_CONTACT_EDGES = {
    "depends_on",
    "sub_knowledge",
    "operator_target",
    "strategy_given",
    "lkm_related",
}

# §3b — frontier contact lifecycle states.
VALID_CONTACT_STATUSES = {"open", "surveyed", "skipped", "deferred"}

# §3b — the two flavours of contact reference.
VALID_REF_KINDS = {"qid", "lkm"}

# §2 — seed origin kinds.
VALID_SEED_KINDS = {"claim", "question"}

# CLIENT.md "Turn state machine" — the orchestrator phase recorded on the map.
# IDLE              : the loop is between turns; the next `gaia-lkm-explore turn` ranks
#                     the frontier, emits a survey task, and sets AWAITING_SURVEY.
# AWAITING_SURVEY   : a task envelope has been emitted; an external agent is
#                     surveying. The map stays here until a result manifest lands.
# AWAITING_CHECKPOINT: a result manifest is present (the orchestrator INFERS this
#                     phase from the manifest's presence — the agent never sets it
#                     by hand); the next `turn` compiles + infers + rounds and
#                     returns to IDLE.
TURN_PHASE_IDLE = "IDLE"
TURN_PHASE_AWAITING_SURVEY = "AWAITING_SURVEY"
TURN_PHASE_AWAITING_CHECKPOINT = "AWAITING_CHECKPOINT"
VALID_TURN_PHASES = {
    TURN_PHASE_IDLE,
    TURN_PHASE_AWAITING_SURVEY,
    TURN_PHASE_AWAITING_CHECKPOINT,
}

# §4 — the DESIGN §4 scoring weight vector keys. A Policy carries exactly these.
# ``w_obligation`` is the build-12 obligation-pressure weight (CLIENT.md steer 3).
POLICY_WEIGHT_KEYS = (
    "w_tension",
    "w_uncertainty",
    "w_bridge",
    "w_coverage",
    "w_relevance",
    "w_cost",
    "w_obligation",
)

# Build 12 (CLIENT.md steer 3): the STRONG default obligation-pressure weight.
# obligation_pressure is binary (0.0 / 1.0), so w_obligation IS the score bump a
# matching contact gets. 1.0 puts it on par with the strongest single live term in
# any preset (w_uncertainty/w_bridge/w_coverage/w_tension all peak at 1.0), so a
# contact discharging an open obligation reliably outranks a non-matching peer all
# else equal — yet it stays a WEIGHTED term, not a hard gate: relevance/coverage/
# uncertainty still count and nothing starves when no obligation matches. Doctrines
# can dial it (all default to the same strong value here).
DEFAULT_W_OBLIGATION = 1.0

# §4 — named doctrine presets (DESIGN §4): a small registry of weight vectors.
# "custom" is NOT in this registry — it carries an explicit weights vector.
DOCTRINE_PRESETS: dict[str, dict[str, float]] = {
    # Cartographer — open fresh territory and connect clusters.
    "Cartographer": {
        "w_tension": 0.0,
        "w_uncertainty": 0.2,
        "w_bridge": 1.0,
        "w_coverage": 1.0,
        "w_relevance": 0.3,
        "w_cost": 0.2,
        "w_obligation": DEFAULT_W_OBLIGATION,
    },
    # Inquisitor — hunt fault lines / contradictions.
    "Inquisitor": {
        "w_tension": 1.0,
        "w_uncertainty": 0.3,
        "w_bridge": 0.0,
        "w_coverage": 0.1,
        "w_relevance": 0.4,
        "w_cost": 0.2,
        "w_obligation": DEFAULT_W_OBLIGATION,
    },
    # Surveyor — reduce uncertainty in the undecided.
    "Surveyor": {
        "w_tension": 0.2,
        "w_uncertainty": 1.0,
        "w_bridge": 0.0,
        "w_coverage": 0.3,
        "w_relevance": 0.4,
        "w_cost": 0.2,
        "w_obligation": DEFAULT_W_OBLIGATION,
    },
    # Diplomat — bridge previously-disjoint clusters.
    "Diplomat": {
        "w_tension": 0.0,
        "w_uncertainty": 0.2,
        "w_bridge": 1.0,
        "w_coverage": 0.3,
        "w_relevance": 0.5,
        "w_cost": 0.2,
        "w_obligation": DEFAULT_W_OBLIGATION,
    },
}


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def mint_contact_id() -> str:
    """Mint a short synthetic frontier-contact id of the form ``ct_<hex8>``."""
    return f"ct_{uuid.uuid4().hex[:8]}"


@dataclass
class SurveyRecord:
    """Exploration overlay on a materialized IR node (SCHEMA.md §3a).

    A node is *surveyed* iff a ``Knowledge`` body exists in the IR (canonical)
    and it has an entry here. This record carries only what the IR lacks:
    exploration provenance + the round that materialized it. Node content,
    type, provenance, and belief are read from the IR / ``beliefs.json`` by
    ``qid`` — never copied here.
    """

    qid: str
    survey_round: int = 0
    lkm_origin: dict[str, Any] = field(default_factory=dict)
    promoted_from_contact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible payload for this survey record."""
        return {
            "qid": self.qid,
            "survey_round": self.survey_round,
            "lkm_origin": dict(self.lkm_origin),
            "promoted_from_contact": self.promoted_from_contact,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SurveyRecord:
        """Rehydrate a survey record from its persisted payload."""
        return cls(
            qid=raw["qid"],
            survey_round=int(raw.get("survey_round", 0)),
            lkm_origin=dict(raw.get("lkm_origin", {})),
            promoted_from_contact=raw.get("promoted_from_contact"),
        )


@dataclass
class Contact:
    """A referenced-but-unexpanded frontier target (SCHEMA.md §3b).

    A contact is a reference *target* that some surveyed node points at but
    which has no materialized ``Knowledge`` body yet — either a QID not authored
    yet or an LKM handle co-retrieved but not pulled into the IR. The frontier
    *is* the fog boundary; fog itself is not stored.

    ``meta`` carries reference-kind-specific extra data the IR does not hold.
    For an ``lkm`` paper-contact (SCHEMA.md §7f) it holds the LKM metadata needed
    to rank and pull the paper: ``paper_id``, ``title``, ``doi``, ``index_id``,
    the max LKM ``rank`` seen, the surfacing ``query``, and the related
    ``lkm_node_ids``. For a ``qid`` contact it is normally empty.
    """

    id: str
    ref: dict[str, Any]
    sources: list[dict[str, Any]] = field(default_factory=list)
    score: float | None = None
    score_features: dict[str, Any] = field(default_factory=dict)
    discovered_round: int = 0
    last_scored_round: int | None = None
    status: str = "open"
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the ref kind, source edges, and lifecycle status."""
        kind = self.ref.get("kind")
        if kind not in VALID_REF_KINDS:
            raise ValueError(
                f"invalid contact ref kind {kind!r}; allowed: {sorted(VALID_REF_KINDS)}"
            )
        if self.status not in VALID_CONTACT_STATUSES:
            raise ValueError(
                f"invalid contact status {self.status!r}; allowed: {sorted(VALID_CONTACT_STATUSES)}"
            )
        for source in self.sources:
            edge = source.get("edge")
            if edge not in VALID_CONTACT_EDGES:
                raise ValueError(
                    f"invalid contact source edge {edge!r}; allowed: {sorted(VALID_CONTACT_EDGES)}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible payload for this contact."""
        return {
            "id": self.id,
            "ref": dict(self.ref),
            "sources": [dict(s) for s in self.sources],
            "score": self.score,
            "score_features": dict(self.score_features),
            "discovered_round": self.discovered_round,
            "last_scored_round": self.last_scored_round,
            "status": self.status,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Contact:
        """Rehydrate a contact from its persisted payload."""
        score = raw.get("score")
        return cls(
            id=raw["id"],
            ref=dict(raw["ref"]),
            sources=[dict(s) for s in raw.get("sources", [])],
            score=None if score is None else float(score),
            score_features=dict(raw.get("score_features", {})),
            discovered_round=int(raw.get("discovered_round", 0)),
            last_scored_round=raw.get("last_scored_round"),
            status=raw.get("status", "open"),
            meta=dict(raw.get("meta", {})),
        )


@dataclass
class Policy:
    """The per-round exploration dial (SCHEMA.md §4).

    ``doctrine`` is a named preset from :data:`DOCTRINE_PRESETS`, or ``"custom"``
    carrying an explicit ``weights`` vector. ``weights`` always holds the full
    :data:`POLICY_WEIGHT_KEYS` vector; ``budget_k`` is the top-k contacts
    surveyed this round.
    """

    doctrine: str = "Cartographer"
    weights: dict[str, float] = field(default_factory=dict)
    budget_k: int = 5

    def __post_init__(self) -> None:
        """Resolve a named doctrine to its preset; validate the weight vector."""
        if self.doctrine != "custom" and not self.weights:
            preset = DOCTRINE_PRESETS.get(self.doctrine)
            if preset is None:
                raise ValueError(
                    f"unknown doctrine {self.doctrine!r}; allowed: "
                    f"{[*sorted(DOCTRINE_PRESETS), 'custom']}"
                )
            self.weights = dict(preset)
        # Back-compat (build 12): maps saved before w_obligation existed (and
        # custom dials that omit it) load with the strong default rather than
        # failing the strict missing-keys check below. New term, additive.
        self.weights.setdefault("w_obligation", DEFAULT_W_OBLIGATION)
        missing = [k for k in POLICY_WEIGHT_KEYS if k not in self.weights]
        if missing:
            raise ValueError(f"policy weights missing keys: {missing}")

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible payload for this policy."""
        return {
            "doctrine": self.doctrine,
            "weights": dict(self.weights),
            "budget_k": self.budget_k,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Policy:
        """Rehydrate a policy from its persisted payload."""
        return cls(
            doctrine=raw.get("doctrine", "Cartographer"),
            weights=dict(raw.get("weights", {})),
            budget_k=int(raw.get("budget_k", 5)),
        )


def doctrine_policy(doctrine: str, budget_k: int = 5) -> Policy:
    """Build a :class:`Policy` from a named doctrine preset (DESIGN §4).

    Args:
        doctrine: A key of :data:`DOCTRINE_PRESETS` (``"custom"`` is rejected
            here — a custom policy must supply its own weights vector).
        budget_k: Top-k contacts to survey in the round.

    Returns:
        A policy whose weights are a copy of the named preset.
    """
    if doctrine not in DOCTRINE_PRESETS:
        raise ValueError(f"unknown doctrine {doctrine!r}; allowed: {sorted(DOCTRINE_PRESETS)}")
    return Policy(doctrine=doctrine, weights=dict(DOCTRINE_PRESETS[doctrine]), budget_k=budget_k)


@dataclass
class ExplorationMap:
    """The top-level exploration overlay persisted at ``map.json`` (SCHEMA.md §2).

    An index/overlay over the IR: ``surveyed`` maps QID → :class:`SurveyRecord`,
    ``frontier`` is the list of open/closed :class:`Contact` targets, ``policy``
    is the current round's dial, and ``stats`` are cheap denormalized counters
    for legibility / render. Fog is the implicit complement and is not stored.
    """

    version: int = EXPLORATION_SCHEMA_VERSION
    created_at: str | None = None
    updated_at: str | None = None
    round: int = 0
    seeds: list[dict[str, Any]] = field(default_factory=list)
    policy: Policy = field(default_factory=Policy)
    surveyed: dict[str, SurveyRecord] = field(default_factory=dict)
    frontier: list[Contact] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    turn_phase: str = TURN_PHASE_IDLE

    def __post_init__(self) -> None:
        """Fill creation/update timestamps; validate the turn phase."""
        if self.created_at is None:
            self.created_at = _utcnow()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.turn_phase not in VALID_TURN_PHASES:
            raise ValueError(
                f"invalid turn_phase {self.turn_phase!r}; allowed: {sorted(VALID_TURN_PHASES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the persisted map payload as a JSON-compatible dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "round": self.round,
            "seeds": [dict(s) for s in self.seeds],
            "policy": self.policy.to_dict(),
            "surveyed": {qid: rec.to_dict() for qid, rec in self.surveyed.items()},
            "frontier": [c.to_dict() for c in self.frontier],
            "stats": dict(self.stats),
            "turn_phase": self.turn_phase,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ExplorationMap:
        """Rehydrate a map from its persisted payload (no version gate here)."""
        return cls(
            version=int(raw.get("version", EXPLORATION_SCHEMA_VERSION)),
            created_at=raw.get("created_at"),
            updated_at=raw.get("updated_at"),
            round=int(raw.get("round", 0)),
            seeds=[dict(s) for s in raw.get("seeds", [])],
            policy=Policy.from_dict(raw.get("policy", {})),
            surveyed={
                qid: SurveyRecord.from_dict(rec) for qid, rec in raw.get("surveyed", {}).items()
            },
            frontier=[Contact.from_dict(c) for c in raw.get("frontier", [])],
            stats=dict(raw.get("stats", {})),
            # Back-compat: a map.json written before turn_phase existed has no
            # such key — default to IDLE so old saves load unchanged.
            turn_phase=raw.get("turn_phase", TURN_PHASE_IDLE),
        )

    def find_contact(self, contact_id: str) -> Contact | None:
        """Return the frontier contact with the given id, or None."""
        for contact in self.frontier:
            if contact.id == contact_id:
                return contact
        return None

    def promote_contact(
        self,
        contact_id: str,
        *,
        survey_round: int,
        lkm_origin: dict[str, Any] | None = None,
    ) -> SurveyRecord:
        """Survey a frontier contact: flip its status and add a SurveyRecord.

        Mirrors SCHEMA.md §3b promotion bookkeeping — the contact flips
        ``status: surveyed`` (kept, not deleted, for round legibility), and a
        :class:`SurveyRecord` carrying ``promoted_from_contact`` is added to
        ``surveyed`` keyed by the contact's QID. Only QID-ref contacts can be
        promoted (an LKM handle has no IR QID until materialized).

        Args:
            contact_id: The frontier contact id to promote.
            survey_round: The round that materialized it.
            lkm_origin: Optional LKM retrieval provenance for the record.

        Returns:
            The newly added survey record.
        """
        contact = self.find_contact(contact_id)
        if contact is None:
            raise KeyError(f"no frontier contact with id {contact_id!r}")
        if contact.ref.get("kind") != "qid":
            raise ValueError(
                f"cannot promote non-qid contact {contact_id!r} "
                f"(ref kind {contact.ref.get('kind')!r}); it has no IR QID yet"
            )
        qid = str(contact.ref["value"])
        contact.status = "surveyed"
        record = SurveyRecord(
            qid=qid,
            survey_round=survey_round,
            lkm_origin=dict(lkm_origin or {}),
            promoted_from_contact=contact_id,
        )
        self.surveyed[qid] = record
        return record


def exploration_dir(pkg_path: str | Path) -> Path:
    """Return the package exploration directory, creating it if needed."""
    d = Path(pkg_path).resolve() / ".gaia" / "exploration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _map_path(pkg_path: str | Path) -> Path:
    return exploration_dir(pkg_path) / "map.json"


def _rounds_path(pkg_path: str | Path) -> Path:
    return exploration_dir(pkg_path) / "rounds.jsonl"


def load_map(pkg_path: str | Path) -> ExplorationMap:
    """Load the persisted exploration map, or return a default empty map.

    Mirrors ``inquiry/state.py``'s version gate: an on-disk ``version`` newer
    than :data:`EXPLORATION_SCHEMA_VERSION` is refused with a ``ValueError`` —
    we never silently downgrade a future artifact.
    """
    p = _map_path(pkg_path)
    if not p.exists():
        return ExplorationMap()
    raw = json.loads(p.read_text(encoding="utf-8"))
    version = int(raw.get("version", 1))
    if version > EXPLORATION_SCHEMA_VERSION:
        raise ValueError(
            f"map.json version {version} is newer than supported {EXPLORATION_SCHEMA_VERSION}"
        )
    return ExplorationMap.from_dict(raw)


def save_map(pkg_path: str | Path, exploration_map: ExplorationMap) -> None:
    """Persist the exploration map atomically to ``.gaia/exploration/map.json``.

    Refreshes ``updated_at`` and writes via ``map.json.tmp`` then
    ``tmp.replace(path)`` (the ``snapshot.py`` atomic-write pattern) so a reader
    never observes a half-written file.
    """
    p = _map_path(pkg_path)
    exploration_map.updated_at = _utcnow()
    payload = exploration_map.to_dict()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def append_round(
    pkg_path: str | Path,
    *,
    round_index: int,
    policy: Policy,
    surveyed: list[str] | None = None,
    discoveries: list[dict[str, Any]] | None = None,
    frontier_summary: dict[str, Any] | None = None,
    lkm_pulls: int = 0,
) -> dict[str, Any]:
    """Append one completed-round record to the append-only round log (§5).

    Mirrors ``append_tactic_event`` — one JSON record per line at
    ``.gaia/exploration/rounds.jsonl``. Enables resume + per-round legibility.

    Returns:
        The record that was written.
    """
    rec = {
        "round": round_index,
        "timestamp": _utcnow(),
        "policy": policy.to_dict(),
        "surveyed": list(surveyed or []),
        "discoveries": [dict(d) for d in (discoveries or [])],
        "frontier_summary": dict(frontier_summary or {}),
        "lkm_pulls": lkm_pulls,
    }
    p = _rounds_path(pkg_path)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def lkm_pulls_this_round(pkg_path: str | Path, materialized_paper_count: int) -> int:
    """Net-new LKM papers materialized this round (the round's ``lkm_pulls``).

    Pulls happen via ``gaia pkg add --lkm-paper`` *during* the survey, outside the
    round step, so a round previously recorded ``lkm_pulls: 0`` even when papers
    were materialized. We credit the round with the papers materialized *since the
    prior round* = the current count of materialized paper QIDs in the joint view
    minus the running total already credited in earlier rounds (the sum of prior
    ``lkm_pulls`` in ``rounds.jsonl``). Floored at ``0`` so a re-run or a
    bookkeeping skew never produces a negative credit.

    Args:
        pkg_path: The knowledge-package directory.
        materialized_paper_count: The count of paper QIDs materialized in the joint
            view at round time (``len(view.materialized_paper_ids | …)``).

    Returns:
        The number of papers to credit this round.
    """
    prior_total = sum(int(rec.get("lkm_pulls", 0) or 0) for rec in read_rounds(pkg_path))
    return max(0, materialized_paper_count - prior_total)


def read_rounds(pkg_path: str | Path) -> list[dict[str, Any]]:
    """Read the append-only round history as JSON records (§5)."""
    p = _rounds_path(pkg_path)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _beliefs_snapshot_path(pkg_path: str | Path, round_index: int) -> Path:
    return exploration_dir(pkg_path) / f"beliefs-round-{round_index}.json"


def save_round_beliefs(
    pkg_path: str | Path,
    round_index: int,
    beliefs: dict[str, float],
) -> None:
    """Snapshot the flattened beliefs a round saw (the prev-round diff baseline).

    Written as a compact ``.gaia/exploration/beliefs-round-<n>.json`` sidecar
    (SCHEMA.md §7c's "compact beliefs snapshot" option, chosen over a
    ``prev_beliefs`` block in the round record so ``rounds.jsonl`` keeps its §5
    shape). The next round loads round ``n``'s snapshot as its diff baseline.
    """
    p = _beliefs_snapshot_path(pkg_path, round_index)
    p.write_text(
        json.dumps({str(k): float(v) for k, v in beliefs.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_round_beliefs(pkg_path: str | Path, round_index: int) -> dict[str, float]:
    """Load a round's beliefs snapshot (the diff baseline), or ``{}`` if absent."""
    p = _beliefs_snapshot_path(pkg_path, round_index)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): float(v) for k, v in raw.items()}
