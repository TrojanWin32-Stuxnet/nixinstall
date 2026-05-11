from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from nixosinstall.models import (
    Bootloader,
    DesktopProfile,
    DiskBackend,
    EncryptionMode,
    Filesystem,
    InstallConfig,
    NetworkMode,
    NixMode,
    ServerProfile,
)


@dataclass(frozen=True)
class GeneratedFile:
    path: PurePosixPath
    content: str


def _nix_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _nix_attr(value: str) -> str:
    return _nix_string(value)


def _nix_list(values: list[str]) -> str:
    if not values:
        return "[ ]"
    return "[ " + " ".join(_nix_string(value) for value in values) + " ]"


def _nix_ident_list(values: list[str]) -> str:
    if not values:
        return "[ ]"
    return "[ " + " ".join(values) + " ]"


class NixConfigRenderer:
    def render(self, config: InstallConfig) -> list[GeneratedFile]:
        files: list[GeneratedFile] = []

        if config.nix.mode in (NixMode.CLASSIC, NixMode.BOTH):
            files.append(GeneratedFile(PurePosixPath("configuration.nix"), self.render_configuration(config)))

        if config.nix.mode in (NixMode.FLAKE, NixMode.BOTH):
            files.append(GeneratedFile(PurePosixPath("flake.nix"), self.render_flake(config)))
            files.append(GeneratedFile(PurePosixPath("system.nix"), self.render_system_module(config)))

        if config.disk.backend == DiskBackend.DISKO:
            files.append(GeneratedFile(PurePosixPath("disko-config.nix"), self.render_disko(config)))

        return files

    def render_configuration(self, config: InstallConfig) -> str:
        imports = ["./hardware-configuration.nix"]

        return self._module(config, imports)

    def render_system_module(self, config: InstallConfig) -> str:
        imports = ["./hardware-configuration.nix"]
        if config.disk.backend == DiskBackend.DISKO:
            imports.append("./disko-config.nix")
        return self._module(config, imports)

    def render_flake(self, config: InstallConfig) -> str:
        if config.disk.backend == DiskBackend.DISKO:
            inputs = f"""  inputs = {{\n    nixpkgs.url = {_nix_string(config.nix.nixpkgs)};\n    disko.url = "github:nix-community/disko";\n    disko.inputs.nixpkgs.follows = "nixpkgs";\n  }};"""
            outputs_args = "self, nixpkgs, disko"
            modules = "[ disko.nixosModules.disko ./system.nix ]"
        else:
            inputs = f"""  inputs.nixpkgs.url = {_nix_string(config.nix.nixpkgs)};"""
            outputs_args = "self, nixpkgs"
            modules = "[ ./system.nix ]"

        return f"""{{\n  description = "Generated NixOS system for {config.network.host_name}";\n\n{inputs}\n\n  outputs = {{ {outputs_args} }}: {{\n    nixosConfigurations.{_nix_attr(config.network.host_name)} = nixpkgs.lib.nixosSystem {{\n      system = {_nix_string(config.nix.system)};\n      modules = {modules};\n    }};\n  }};\n}}\n"""

    def render_disko(self, config: InstallConfig) -> str:
        filesystem_content = self._disko_filesystem_content(config)
        if config.disk.encryption == EncryptionMode.LVM_ON_LUKS:
            swap_lv = ""
            if config.disk.swap_size:
                swap_lv = f"""\n      lvs.swap = {{\n        size = {_nix_string(config.disk.swap_size)};\n        content.type = "swap";\n      }};"""
            root_content = f"""{{\n                    type = "luks";\n                    name = "crypted";\n                    content = {{\n                      type = "lvm_pv";\n                      vg = "vg";\n                    }};\n                  }}"""
            extra_lvm = f"""\n    lvm_vg.vg = {{\n      type = "lvm_vg";{swap_lv}\n      lvs.root = {{\n        size = "100%FREE";\n        content = {filesystem_content.rstrip()};\n      }};\n    }};"""
        elif config.disk.encryption == EncryptionMode.LUKS:
            root_content = f"""{{\n                    type = "luks";\n                    name = "crypted";\n                    content = {filesystem_content.rstrip()};\n                  }}"""
            extra_lvm = ""
        else:
            root_content = filesystem_content
            extra_lvm = ""

        swap_partition = ""
        if config.disk.swap_size and config.disk.encryption != EncryptionMode.LVM_ON_LUKS:
            swap_partition = f"""\n          swap = {{\n            size = {_nix_string(config.disk.swap_size)};\n            content.type = "swap";\n          }};"""

        return f"""{{ ... }}:\n{{\n  disko.devices = {{\n    disk.main = {{\n      device = {_nix_string(config.disk.device)};\n      type = "disk";\n      content = {{\n        type = "gpt";\n        partitions = {{\n          ESP = {{\n            size = {_nix_string(config.disk.boot_size)};\n            type = "EF00";\n            content = {{\n              type = "filesystem";\n              format = "vfat";\n              mountpoint = "/boot";\n              mountOptions = [ "umask=0077" ];\n            }};\n          }};{swap_partition}\n          root = {{\n            size = "100%";\n            content = {root_content.rstrip()};\n          }};\n        }};\n      }};\n    }};{extra_lvm}\n  }};\n}}\n"""

    def _disko_filesystem_content(self, config: InstallConfig) -> str:
        mount_options = ""
        if config.disk.filesystem == Filesystem.BTRFS:
            mount_options = '\n                      mountOptions = [ "compress=zstd" "noatime" ];'
        return f"""{{\n                      type = "filesystem";\n                      format = {_nix_string(config.disk.filesystem.value)};\n                      mountpoint = "/";{mount_options}\n                    }}"""

    def _module(self, config: InstallConfig, imports: list[str]) -> str:
        lines = [
            "{ config, pkgs, ... }:",
            "{",
            "  imports = [",
        ]

        lines.extend(f"    {item}" for item in imports)
        lines.append("  ];")
        lines.extend(
            [
                "",
                f"  networking.hostName = {_nix_string(config.network.host_name)};",
                f"  time.timeZone = {_nix_string(config.locale.timezone)};",
                f"  i18n.defaultLocale = {_nix_string(config.locale.language)};",
                f"  console.keyMap = {_nix_string(config.locale.keyboard)};",
                "",
                f"  nix.settings.experimental-features = {_nix_list(config.experimental_features)};",
            ]
        )

        lines.extend(self._bootloader_lines(config))
        lines.extend(self._network_lines(config))
        lines.extend(self._profile_lines(config))
        lines.extend(self._user_lines(config))
        lines.extend(self._package_lines(config))
        lines.extend(self._service_lines(config))
        lines.extend(
            [
                "",
                '  system.stateVersion = "25.05";',
                "}",
                "",
            ]
        )
        return "\n".join(lines)

    def _bootloader_lines(self, config: InstallConfig) -> list[str]:
        if config.bootloader == Bootloader.NONE:
            return ["", "  boot.loader.grub.enable = false;"]
        if config.bootloader == Bootloader.GRUB:
            return [
                "",
                "  boot.loader.grub.enable = true;",
                f"  boot.loader.grub.device = {_nix_string(config.disk.device)};",
            ]
        return [
            "",
            "  boot.loader.systemd-boot.enable = true;",
            "  boot.loader.efi.canTouchEfiVariables = true;",
        ]

    def _network_lines(self, config: InstallConfig) -> list[str]:
        if config.network.mode == NetworkMode.NONE:
            return ["", "  networking.networkmanager.enable = false;"]
        if config.network.mode == NetworkMode.NETWORK_MANAGER:
            return ["", "  networking.networkmanager.enable = true;"]

        lines = ["", "  networking.useDHCP = false;"]
        if config.network.interface and config.network.address:
            lines.extend(
                [
                    f"  networking.interfaces.{_nix_attr(config.network.interface)}.ipv4.addresses = [ {{",
                    f"    address = {_nix_string(config.network.address.split('/')[0])};",
                    f"    prefixLength = {config.network.address.split('/')[1] if '/' in config.network.address else '24'};",
                    "  } ];",
                ]
            )
        if config.network.gateway:
            lines.append(f"  networking.defaultGateway = {_nix_string(config.network.gateway)};")
        if config.network.dns:
            lines.append(f"  networking.nameservers = {_nix_list(config.network.dns)};")
        return lines

    def _profile_lines(self, config: InstallConfig) -> list[str]:
        lines = [""]
        match config.desktop:
            case DesktopProfile.GNOME:
                lines.extend(
                    [
                        "  services.xserver.enable = true;",
                        "  services.xserver.displayManager.gdm.enable = true;",
                        "  services.xserver.desktopManager.gnome.enable = true;",
                    ]
                )
            case DesktopProfile.PLASMA:
                lines.extend(
                    [
                        "  services.xserver.enable = true;",
                        "  services.displayManager.sddm.enable = true;",
                        "  services.desktopManager.plasma6.enable = true;",
                    ]
                )
            case DesktopProfile.XFCE:
                lines.extend(
                    [
                        "  services.xserver.enable = true;",
                        "  services.xserver.displayManager.lightdm.enable = true;",
                        "  services.xserver.desktopManager.xfce.enable = true;",
                    ]
                )
            case DesktopProfile.MINIMAL:
                lines.append("  # Minimal profile selected.")

        server_options = {
            ServerProfile.SSH: "services.openssh.enable = true;",
            ServerProfile.DOCKER: "virtualisation.docker.enable = true;",
            ServerProfile.PODMAN: "virtualisation.podman.enable = true;",
            ServerProfile.NGINX: "services.nginx.enable = true;",
            ServerProfile.POSTGRESQL: "services.postgresql.enable = true;",
        }
        lines.extend(f"  {server_options[server]}" for server in config.servers)
        return lines

    def _user_lines(self, config: InstallConfig) -> list[str]:
        lines = [""]
        for user in config.users:
            groups = ["networkmanager"]
            if user.wheel:
                groups.append("wheel")
            lines.extend(
                [
                    f"  users.users.{_nix_attr(user.username)} = {{",
                    "    isNormalUser = true;",
                    f"    extraGroups = {_nix_list(groups)};",
                ]
            )
            if user.hashed_password:
                lines.append(f"    hashedPassword = {_nix_string(user.hashed_password)};")
            lines.append("  };")
        return lines

    def _package_lines(self, config: InstallConfig) -> list[str]:
        packages = sorted(set(config.packages))
        if not packages:
            return ["", "  environment.systemPackages = [ ];"]
        return ["", f"  environment.systemPackages = with pkgs; {_nix_ident_list(packages)};"]

    def _service_lines(self, config: InstallConfig) -> list[str]:
        return [""] + [f"  systemd.services.{_nix_attr(service)}.wantedBy = [ \"multi-user.target\" ];" for service in config.services]
