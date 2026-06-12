"""Public LKM API surface."""

from __future__ import annotations

from gaia.lkm.client import (
    BASE_URL,
    LKMClient,
    LKMCredentialError,
    LKMError,
    LKMNotFoundError,
    LKMPermissionError,
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.lkm.credentials import (
    CredentialPermissionError,
    LKMCredentialPermissionError,
    LKMCredentialSource,
    LKMCredentialStatus,
    active_lkm_env_var,
    credential_status,
    credentials_path,
    lkm_key_status,
    mask_key,
    purge_lkm_key,
    read_lkm_key,
    write_lkm_key,
)
from gaia.lkm.indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)

__all__ = [
    "BASE_URL",
    "DEFAULT_LKM_INDEX_ID",
    "CredentialPermissionError",
    "LKMClient",
    "LKMCredentialError",
    "LKMCredentialPermissionError",
    "LKMCredentialSource",
    "LKMCredentialStatus",
    "LKMError",
    "LKMNotFoundError",
    "LKMPermissionError",
    "LKMTransportError",
    "NoAccessKeyError",
    "active_lkm_env_var",
    "credential_status",
    "credentials_path",
    "known_lkm_index_ids",
    "lkm_index_base_url",
    "lkm_key_status",
    "mask_key",
    "normalize_lkm_index_id",
    "purge_lkm_key",
    "read_lkm_key",
    "write_lkm_key",
]
