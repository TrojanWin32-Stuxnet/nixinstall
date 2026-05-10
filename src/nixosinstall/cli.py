from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nixosinstall.backends import InstallPlan, build_install_plan, execute_commands, write_generated_files
from nixosinstall.config_io import load_config, load_credentials, save_config_bundle
from nixosinstall.models import DiskBackend, NixMode
from nixosinstall.tui import collect_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guided NixOS installer prototype")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--creds", type=Path, help="JSON credentials file")
    parser.add_argument("--dry-run", action="store_true", help="Print generated files and commands without executing")
    parser.add_argument("--silent", action="store_true", help="Skip the guided TUI and use defaults/config files")
    parser.add_argument("--yes", action="store_true", help="Confirm execution of planned destructive install commands")
    parser.add_argument("--disk-backend", choices=[item.value for item in DiskBackend], help="Disk preparation backend")
    parser.add_argument("--nix-mode", choices=[item.value for item in NixMode], help="NixOS output style")
    parser.add_argument("--save-config", type=Path, help="Save user_configuration.json to this directory")
    parser.add_argument("--output-dir", type=Path, help="Write generated Nix files here instead of /mnt/etc/nixos")
    return parser


def plan_to_text(plan: InstallPlan) -> str:
    lines = ["Generated files:"]
    for file in plan.files:
        lines.append(f"  - {file.path}")

    lines.append("")
    lines.append("Planned commands:")
    for command in plan.commands:
        marker = " [destructive]" if command.destructive else ""
        lines.append(f"  - {command.description}{marker}")
        lines.append(f"    {command.shell_text()}")

    lines.append("")
    lines.append("File previews:")
    for file in plan.files:
        lines.append(f"--- {file.path} ---")
        lines.append(file.content.rstrip())
        lines.append("")

    return "\n".join(lines)


def _apply_cli_overrides(args: argparse.Namespace) -> None:
    if args.disk_backend:
        args.config_obj.disk.backend = DiskBackend(args.disk_backend)
    if args.nix_mode:
        args.config_obj.nix.mode = NixMode(args.nix_mode)


def _default_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return args.output_dir
    return Path(args.config_obj.disk.mountpoint) / "etc" / "nixos"


def _write_disko_temp_files(plan: InstallPlan) -> None:
    disko_files = [file for file in plan.files if file.path.name == "disko-config.nix"]
    if disko_files:
        write_generated_files(disko_files, Path("/tmp/nixosinstall"))


def _write_target_files(plan: InstallPlan, target_dir: Path) -> None:
    write_generated_files(plan.files, target_dir)


def _confirm_execution(plan: InstallPlan) -> bool:
    destructive = [command for command in plan.commands if command.destructive]
    if not destructive:
        return True

    print(plan_to_text(plan))
    print("This install plan contains destructive commands.")
    response = input("Type 'yes' to partition disks and install NixOS: ")
    return response == "yes"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    credentials = load_credentials(args.creds)
    args.config_obj = config
    _apply_cli_overrides(args)

    if not args.silent:
        config = asyncio.run(collect_config(config))
        args.config_obj = config

    if args.save_config:
        save_config_bundle(config, credentials, args.save_config, include_credentials=False)

    plan = build_install_plan(config)

    if args.dry_run:
        print(plan_to_text(plan))
        return 0

    if not args.yes and not _confirm_execution(plan):
        print("Aborted.")
        return 2

    target_dir = _default_output_dir(args)
    _write_disko_temp_files(plan)
    execute_commands(plan.disk_commands)
    execute_commands(plan.config_commands)
    _write_target_files(plan, target_dir)
    execute_commands(plan.install_commands)
    return 0
