from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self


class DiskBackend(StrEnum):
    DISKO = "disko"
    IMPERATIVE = "imperative"


class NixMode(StrEnum):
    FLAKE = "flake"
    CLASSIC = "classic"
    BOTH = "both"


class DiskLayout(StrEnum):
    DEFAULT = "default"
    MANUAL = "manual"
    PRE_MOUNTED = "pre-mounted"


class Filesystem(StrEnum):
    EXT4 = "ext4"
    BTRFS = "btrfs"
    XFS = "xfs"


class EncryptionMode(StrEnum):
    NONE = "none"
    LUKS = "luks"
    LVM_ON_LUKS = "lvm-on-luks"


class Bootloader(StrEnum):
    SYSTEMD_BOOT = "systemd-boot"
    GRUB = "grub"
    NONE = "none"


class NetworkMode(StrEnum):
    NETWORK_MANAGER = "networkmanager"
    MANUAL = "manual"
    NONE = "none"


class DesktopProfile(StrEnum):
    MINIMAL = "minimal"
    GNOME = "gnome"
    PLASMA = "plasma"
    XFCE = "xfce"


class ServerProfile(StrEnum):
    SSH = "ssh"
    DOCKER = "docker"
    PODMAN = "podman"
    NGINX = "nginx"
    POSTGRESQL = "postgresql"


@dataclass
class UserAccount:
    username: str = "nixos"
    wheel: bool = True
    hashed_password: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            username=data.get("username", "nixos"),
            wheel=bool(data.get("wheel", True)),
            hashed_password=data.get("hashed_password"),
        )


@dataclass
class Credentials:
    root_password: str | None = None
    user_passwords: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            root_password=data.get("root_password"),
            user_passwords=dict(data.get("user_passwords", {})),
        )

    @classmethod
    def load(cls, path: Path | None) -> Self:
        if path is None:
            return cls()
        return cls.from_dict(json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))


@dataclass
class DiskConfig:
    backend: DiskBackend = DiskBackend.DISKO
    layout: DiskLayout = DiskLayout.DEFAULT
    device: str = "/dev/sda"
    filesystem: Filesystem = Filesystem.EXT4
    encryption: EncryptionMode = EncryptionMode.NONE
    mountpoint: str = "/mnt"
    boot_size: str = "1G"
    swap_size: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            backend=DiskBackend(data.get("backend", DiskBackend.DISKO)),
            layout=DiskLayout(data.get("layout", DiskLayout.DEFAULT)),
            device=data.get("device", "/dev/sda"),
            filesystem=Filesystem(data.get("filesystem", Filesystem.EXT4)),
            encryption=EncryptionMode(data.get("encryption", EncryptionMode.NONE)),
            mountpoint=data.get("mountpoint", "/mnt"),
            boot_size=data.get("boot_size", "1G"),
            swap_size=data.get("swap_size"),
        )


@dataclass
class LocaleConfig:
    language: str = "en_US.UTF-8"
    keyboard: str = "us"
    timezone: str = "UTC"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            language=data.get("language", "en_US.UTF-8"),
            keyboard=data.get("keyboard", "us"),
            timezone=data.get("timezone", "UTC"),
        )


@dataclass
class NetworkConfig:
    mode: NetworkMode = NetworkMode.NETWORK_MANAGER
    host_name: str = "nixos"
    interface: str | None = None
    address: str | None = None
    gateway: str | None = None
    dns: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            mode=NetworkMode(data.get("mode", NetworkMode.NETWORK_MANAGER)),
            host_name=data.get("host_name", "nixos"),
            interface=data.get("interface"),
            address=data.get("address"),
            gateway=data.get("gateway"),
            dns=list(data.get("dns", [])),
        )


@dataclass
class NixSettings:
    mode: NixMode = NixMode.BOTH
    nixpkgs: str = "github:NixOS/nixpkgs/nixos-unstable"
    system: str = "x86_64-linux"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            mode=NixMode(data.get("mode", NixMode.BOTH)),
            nixpkgs=data.get("nixpkgs", "github:NixOS/nixpkgs/nixos-unstable"),
            system=data.get("system", "x86_64-linux"),
        )


@dataclass
class InstallConfig:
    disk: DiskConfig = field(default_factory=DiskConfig)
    locale: LocaleConfig = field(default_factory=LocaleConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    nix: NixSettings = field(default_factory=NixSettings)
    bootloader: Bootloader = Bootloader.SYSTEMD_BOOT
    users: list[UserAccount] = field(default_factory=lambda: [UserAccount()])
    desktop: DesktopProfile = DesktopProfile.MINIMAL
    servers: list[ServerProfile] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    experimental_features: list[str] = field(default_factory=lambda: ["nix-command", "flakes"])

    @classmethod
    def default(cls) -> Self:
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            disk=DiskConfig.from_dict(data.get("disk", {})),
            locale=LocaleConfig.from_dict(data.get("locale", {})),
            network=NetworkConfig.from_dict(data.get("network", {})),
            nix=NixSettings.from_dict(data.get("nix", {})),
            bootloader=Bootloader(data.get("bootloader", Bootloader.SYSTEMD_BOOT)),
            users=[UserAccount.from_dict(u) for u in data.get("users", [{"username": "nixos", "wheel": True}])],
            desktop=DesktopProfile(data.get("desktop", DesktopProfile.MINIMAL)),
            servers=[ServerProfile(s) for s in data.get("servers", [])],
            packages=list(data.get("packages", [])),
            services=list(data.get("services", [])),
            experimental_features=list(data.get("experimental_features", ["nix-command", "flakes"])),
        )

    @classmethod
    def load(cls, path: Path | None) -> Self:
        if path is None:
            return cls.default()
        return cls.from_dict(json.loads(path.read_text()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))
