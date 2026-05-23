"""gaia.engine.exploration — the fog-of-war map-state "save-game" schema.

The durable overlay the exploration machine rides on (SCHEMA.md §2 through §7): a
versioned ``.gaia/exploration/map.json`` index over the IR plus an append-only
``rounds.jsonl`` history. A NEW sibling to ``.gaia/inquiry/``; it never mutates
the IR / priors / ``beliefs.json``. This package is the pure library surface —
the policy scorer, the turn loop, and render live in later sequenced steps and
import from here. Build 2 adds :mod:`gaia.engine.exploration.frontier`, which
derives the frontier from a package's IR (SCHEMA.md §7a). Build 3 adds
:mod:`gaia.engine.exploration.scorer`, which scores the frontier per the current
round's policy dial (SCHEMA.md §7b). Build 4d adds
:mod:`gaia.engine.exploration.observe`, which turns ``gaia search lkm`` results
into ``lkm_related`` paper-contacts — the primary frontier source (SCHEMA.md §7f).
"""

from gaia.engine.exploration.frontier import (
    build_joint_view,
    extract_frontier,
    reconcile_frontier,
)
from gaia.engine.exploration.handoff import (
    SurveyResult,
    SurveyTask,
    TaskContact,
    result_path,
    task_path,
)
from gaia.engine.exploration.observe import (
    ObserveResult,
    observe_lkm_results,
    promote_materialized_lkm_contacts,
)
from gaia.engine.exploration.render import (
    exploration_header_fields,
    frontier_graph_elements,
    inject_exploration_header,
    wrap_self_contained_html,
)
from gaia.engine.exploration.scorer import (
    binary_entropy,
    score_frontier,
)
from gaia.engine.exploration.state import (
    DOCTRINE_PRESETS,
    EXPLORATION_SCHEMA_VERSION,
    POLICY_WEIGHT_KEYS,
    TURN_PHASE_AWAITING_CHECKPOINT,
    TURN_PHASE_AWAITING_SURVEY,
    TURN_PHASE_IDLE,
    VALID_CONTACT_EDGES,
    VALID_CONTACT_STATUSES,
    VALID_REF_KINDS,
    VALID_SEED_KINDS,
    VALID_TURN_PHASES,
    Contact,
    ExplorationMap,
    Policy,
    SurveyRecord,
    append_round,
    doctrine_policy,
    exploration_dir,
    load_map,
    load_round_beliefs,
    mint_contact_id,
    read_rounds,
    save_map,
    save_round_beliefs,
)

__all__ = [
    "DOCTRINE_PRESETS",
    "EXPLORATION_SCHEMA_VERSION",
    "POLICY_WEIGHT_KEYS",
    "TURN_PHASE_AWAITING_CHECKPOINT",
    "TURN_PHASE_AWAITING_SURVEY",
    "TURN_PHASE_IDLE",
    "VALID_CONTACT_EDGES",
    "VALID_CONTACT_STATUSES",
    "VALID_REF_KINDS",
    "VALID_SEED_KINDS",
    "VALID_TURN_PHASES",
    "Contact",
    "ExplorationMap",
    "ObserveResult",
    "Policy",
    "SurveyRecord",
    "SurveyResult",
    "SurveyTask",
    "TaskContact",
    "append_round",
    "binary_entropy",
    "build_joint_view",
    "doctrine_policy",
    "exploration_dir",
    "exploration_header_fields",
    "extract_frontier",
    "frontier_graph_elements",
    "inject_exploration_header",
    "load_map",
    "load_round_beliefs",
    "mint_contact_id",
    "observe_lkm_results",
    "promote_materialized_lkm_contacts",
    "read_rounds",
    "reconcile_frontier",
    "result_path",
    "save_map",
    "save_round_beliefs",
    "score_frontier",
    "task_path",
    "wrap_self_contained_html",
]
