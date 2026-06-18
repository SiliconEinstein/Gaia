"""Backward-compatible CLI imports for LKM credential helpers."""

from __future__ import annotations

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

__all__ = [
    "CredentialPermissionError",
    "LKMCredentialPermissionError",
    "LKMCredentialSource",
    "LKMCredentialStatus",
    "active_lkm_env_var",
    "credential_status",
    "credentials_path",
    "lkm_key_status",
    "mask_key",
    "purge_lkm_key",
    "read_lkm_key",
    "write_lkm_key",
]
