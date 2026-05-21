"""gaia.engine.exploration — the fog-of-war map-state "save-game" schema.

The durable overlay the exploration machine rides on (SCHEMA.md §2 through §7): a
versioned ``.gaia/exploration/map.json`` index over the IR plus an append-only
``rounds.jsonl`` history. A NEW sibling to ``.gaia/inquiry/``; it never mutates
the IR / priors / ``beliefs.json``. This package is the pure library surface —
frontier extraction, the policy scorer, the turn loop, and render live in later
sequenced steps and import from here.
"""

from gaia.engine.exploration.state import (
    DOCTRINE_PRESETS,
    EXPLORATION_SCHEMA_VERSION,
    POLICY_WEIGHT_KEYS,
    VALID_CONTACT_EDGES,
    VALID_CONTACT_STATUSES,
    VALID_REF_KINDS,
    VALID_SEED_KINDS,
    Contact,
    ExplorationMap,
    Policy,
    SurveyRecord,
    append_round,
    doctrine_policy,
    exploration_dir,
    load_map,
    mint_contact_id,
    read_rounds,
    save_map,
)

__all__ = [
    "DOCTRINE_PRESETS",
    "EXPLORATION_SCHEMA_VERSION",
    "POLICY_WEIGHT_KEYS",
    "VALID_CONTACT_EDGES",
    "VALID_CONTACT_STATUSES",
    "VALID_REF_KINDS",
    "VALID_SEED_KINDS",
    "Contact",
    "ExplorationMap",
    "Policy",
    "SurveyRecord",
    "append_round",
    "doctrine_policy",
    "exploration_dir",
    "load_map",
    "mint_contact_id",
    "read_rounds",
    "save_map",
]
