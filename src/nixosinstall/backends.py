from __future__ import annotations

import subprocess
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nixosinstall.models import DiskBackend, DiskConfig, DiskLayout, EncryptionMode, InstallConfig, NixMode
from nixosinstall.nix import GeneratedFile, NixConfigRenderer


@dataclass(frozen=True)
class PlannedCommand:
    argv: list[str]
    description: str
    destructive: bool = False

    def shell_text(self) -> str:
        return shlex.join(self.argv)


@dataclass(frozen=True)
class InstallPlan:
    files: list[GeneratedFile]
    disk_commands: list[PlannedCommand]
    config_commands: list[PlannedCommand]
    install_commands: list[PlannedCommand]

    @property
    def commands(self) -> list[PlannedCommand]:
        return [*self.disk_commands, *self.config_commands, *self.install_commands]


class CommandRunner(Protocol):
    def run(self, command: PlannedCommand) -> None: ...


class SubprocessRunner:
    def run(self, command: PlannedCommand) -> None:
        subprocess.run(command.argv, check=True)


class DiskBackendPlanner(Protocol):
    def plan(self, config: InstallConfig) -> list[PlannedCommand]: ...


class DiskoBackend:
    def plan(self, config: InstallConfig) -> list[PlannedCommand]:
        return [
            PlannedCommand(
                [
                    "nix",
                    "--experimental-features",
                    "nix-command flakes",
                    "run",
                    "github:nix-community/disko/latest",
                    "--",
                    "--mode",
                    "destroy,format,mount",
                    "/tmp/nixosinstall/disko-config.nix",
                ],
                "Partition, format, and mount target disk with disko",
                destructive=True,
            )
        ]


class ImperativeDiskBackend:
    def plan(self, config: InstallConfig) -> list[PlannedCommand]:
        disk = config.disk
        if disk.layout == DiskLayout.PRE_MOUNTED:
            return [
                PlannedCommand(
                    ["findmnt", disk.mountpoint],
                    "Verify pre-mounted target exists",
                )
            ]

        boot_part = partition_path(disk.device, 1)
        root_part = partition_path(disk.device, 2)
        swap_part = partition_path(disk.device, 3)
        root_partition_end = f"-{disk.swap_size}" if disk.swap_size else "0"
        commands = [
            PlannedCommand(["sgdisk", "--zap-all", disk.device], "Wipe partition table", destructive=True),
            PlannedCommand(["sgdisk", "-n", f"1:1MiB:+{disk.boot_size}", "-t", "1:EF00", disk.device], "Create EFI system partition", destructive=True),
            PlannedCommand(["sgdisk", "-n", f"2:0:{root_partition_end}", "-t", "2:8300", disk.device], "Create root partition", destructive=True),
            PlannedCommand(["mkfs.vfat", "-F", "32", boot_part], "Format EFI system partition", destructive=True),
        ]
        if disk.swap_size and disk.encryption != EncryptionMode.LVM_ON_LUKS:
            commands.extend(
                [
                    PlannedCommand(["sgdisk", "-n", "3:0:0", "-t", "3:8200", disk.device], "Create swap partition", destructive=True),
                    PlannedCommand(["mkswap", swap_part], "Format swap partition", destructive=True),
                    PlannedCommand(["swapon", swap_part], "Enable swap partition", destructive=True),
                ]
            )

        if disk.encryption == EncryptionMode.NONE:
            commands.extend(self._root_format_mount_commands(disk, root_part))
        elif disk.encryption == EncryptionMode.LUKS:
            commands.extend(
                [
                    PlannedCommand(["cryptsetup", "luksFormat", root_part], "Create LUKS container", destructive=True),
                    PlannedCommand(["cryptsetup", "open", root_part, "crypted"], "Open LUKS container", destructive=True),
                    *self._root_format_mount_commands(disk, "/dev/mapper/crypted"),
                ]
            )
        else:
            commands.extend(self._lvm_on_luks_commands(disk, root_part))

        commands.extend(
            [
                PlannedCommand(["mkdir", "-p", f"{disk.mountpoint}/boot"], "Create boot mountpoint"),
                PlannedCommand(["mount", boot_part, f"{disk.mountpoint}/boot"], "Mount EFI partition", destructive=True),
            ]
        )
        return commands

    def _root_format_mount_commands(self, disk: DiskConfig, root_device: str) -> list[PlannedCommand]:
        return [
            PlannedCommand([f"mkfs.{disk.filesystem.value}", root_device], "Format root filesystem", destructive=True),
            PlannedCommand(["mount", root_device, disk.mountpoint], "Mount root filesystem", destructive=True),
        ]

    def _lvm_on_luks_commands(self, disk: DiskConfig, root_part: str) -> list[PlannedCommand]:
        commands = [
            PlannedCommand(["cryptsetup", "luksFormat", root_part], "Create LUKS container", destructive=True),
            PlannedCommand(["cryptsetup", "open", root_part, "crypted"], "Open LUKS container", destructive=True),
            PlannedCommand(["pvcreate", "/dev/mapper/crypted"], "Create LVM physical volume", destructive=True),
            PlannedCommand(["vgcreate", "nixos-vg", "/dev/mapper/crypted"], "Create LVM volume group", destructive=True),
        ]
        if disk.swap_size:
            commands.extend(
                [
                    PlannedCommand(["lvcreate", "-L", disk.swap_size, "-n", "swap", "nixos-vg"], "Create swap logical volume", destructive=True),
                    PlannedCommand(["mkswap", "/dev/nixos-vg/swap"], "Format swap logical volume", destructive=True),
                    PlannedCommand(["swapon", "/dev/nixos-vg/swap"], "Enable swap logical volume", destructive=True),
                ]
            )
        commands.extend(
            [
                PlannedCommand(["lvcreate", "-l", "100%FREE", "-n", "root", "nixos-vg"], "Create root logical volume", destructive=True),
                *self._root_format_mount_commands(disk, "/dev/nixos-vg/root"),
            ]
        )
        return commands


class InstallerBackend:
    def config_plan(self, config: InstallConfig) -> list[PlannedCommand]:
        return [
            PlannedCommand(["mkdir", "-p", f"{config.disk.mountpoint}/etc/nixos"], "Create NixOS config directory"),
            PlannedCommand(
                ["nixos-generate-config", "--root", config.disk.mountpoint],
                "Generate hardware-configuration.nix",
            )
        ]

    def install_plan(self, config: InstallConfig) -> list[PlannedCommand]:
        commands = []
        if config.nix.mode == NixMode.FLAKE:
            commands.append(self._flake_install(config))
        elif config.nix.mode == NixMode.BOTH:
            commands.append(self._flake_install(config))
        else:
            commands.append(
                PlannedCommand(
                    ["nixos-install", "--root", config.disk.mountpoint],
                    "Install NixOS from classic configuration",
                    destructive=True,
                )
            )
        return commands

    def _flake_install(self, config: InstallConfig) -> PlannedCommand:
        return PlannedCommand(
            [
                "nixos-install",
                "--root",
                config.disk.mountpoint,
                "--flake",
                f"{config.disk.mountpoint}/etc/nixos#{config.network.host_name}",
            ],
            "Install NixOS from flake configuration",
            destructive=True,
        )


def disk_backend_for(config: InstallConfig) -> DiskBackendPlanner:
    if config.disk.backend == DiskBackend.IMPERATIVE:
        return ImperativeDiskBackend()
    return DiskoBackend()


def partition_path(device: str, number: int) -> str:
    if device[-1:].isdigit():
        return f"{device}p{number}"
    return f"{device}{number}"


def build_install_plan(config: InstallConfig) -> InstallPlan:
    renderer = NixConfigRenderer()
    installer = InstallerBackend()
    files = renderer.render(config)
    disk_commands = disk_backend_for(config).plan(config)
    config_commands = installer.config_plan(config)
    install_commands = installer.install_plan(config)
    return InstallPlan(files=files, disk_commands=disk_commands, config_commands=config_commands, install_commands=install_commands)


def write_generated_files(files: list[GeneratedFile], target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        path = target_dir / str(file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content)


def execute_commands(commands: list[PlannedCommand], runner: CommandRunner | None = None) -> None:
    runner = runner or SubprocessRunner()
    for command in commands:
        runner.run(command)


def execute_plan(plan: InstallPlan, runner: CommandRunner | None = None) -> None:
    execute_commands(plan.commands, runner)
