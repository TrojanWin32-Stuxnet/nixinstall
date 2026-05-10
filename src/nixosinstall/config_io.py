from __future__ import annotations

from pathlib import Path

from nixosinstall.models import Credentials, InstallConfig


USER_CONFIG = "user_configuration.json"
USER_CREDS = "user_credentials.json"


def load_config(config_path: Path | None) -> InstallConfig:
    return InstallConfig.load(config_path)


def load_credentials(creds_path: Path | None) -> Credentials:
    return Credentials.load(creds_path)


def save_config_bundle(config: InstallConfig, credentials: Credentials, directory: Path, include_credentials: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    config.save(directory / USER_CONFIG)
    if include_credentials:
        credentials.save(directory / USER_CREDS)
