from nixosinstall.backends import build_install_plan, partition_path
from nixosinstall.models import DiskBackend, EncryptionMode, InstallConfig, NixMode


def test_disko_plan_uses_disko_command():
    config = InstallConfig.default()

    plan = build_install_plan(config)

    assert plan.disk_commands[0].argv[:4] == ["nix", "--experimental-features", "nix-command flakes", "run"]
    assert "github:nix-community/disko/latest" in plan.disk_commands[0].argv
    assert plan.disk_commands[0].destructive is True


def test_imperative_plan_uses_partition_commands():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE

    plan = build_install_plan(config)

    commands = [command.argv[0] for command in plan.disk_commands]
    assert "sgdisk" in commands
    assert "mkfs.vfat" in commands
    assert "mount" in commands


def test_imperative_plan_uses_nvme_partition_names():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE
    config.disk.device = "/dev/nvme0n1"

    plan = build_install_plan(config)

    rendered = [command.shell_text() for command in plan.disk_commands]
    assert "mkfs.vfat -F 32 /dev/nvme0n1p1" in rendered
    assert "mkfs.ext4 /dev/nvme0n1p2" in rendered


def test_partition_path_handles_common_device_names():
    assert partition_path("/dev/sda", 2) == "/dev/sda2"
    assert partition_path("/dev/vda", 2) == "/dev/vda2"
    assert partition_path("/dev/nvme0n1", 2) == "/dev/nvme0n1p2"
    assert partition_path("/dev/mmcblk0", 2) == "/dev/mmcblk0p2"


def test_imperative_plan_can_create_swap():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE
    config.disk.swap_size = "8G"

    plan = build_install_plan(config)

    rendered = [command.shell_text() for command in plan.disk_commands]
    assert "sgdisk -n 3:0:0 -t 3:8200 /dev/sda" in rendered
    assert "mkswap /dev/sda3" in rendered
    assert "swapon /dev/sda3" in rendered


def test_imperative_plan_supports_lvm_on_luks():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE
    config.disk.encryption = EncryptionMode.LVM_ON_LUKS
    config.disk.swap_size = "4G"

    plan = build_install_plan(config)

    rendered = [command.shell_text() for command in plan.disk_commands]
    assert "pvcreate /dev/mapper/crypted" in rendered
    assert "vgcreate nixos-vg /dev/mapper/crypted" in rendered
    assert "lvcreate -L 4G -n swap nixos-vg" in rendered
    assert "mkfs.ext4 /dev/nixos-vg/root" in rendered


def test_classic_install_uses_plain_nixos_install():
    config = InstallConfig.default()
    config.nix.mode = NixMode.CLASSIC

    plan = build_install_plan(config)

    install = plan.install_commands[-1]
    assert install.argv == ["nixos-install", "--root", "/mnt"]


def test_both_mode_prefers_flake_install():
    config = InstallConfig.default()

    plan = build_install_plan(config)

    install = plan.install_commands[-1]
    assert "--flake" in install.argv
    assert "/mnt/etc/nixos#nixos" in install.argv


def test_plan_separates_config_generation_from_install():
    config = InstallConfig.default()

    plan = build_install_plan(config)

    assert plan.config_commands[0].argv == ["mkdir", "-p", "/mnt/etc/nixos"]
    assert plan.config_commands[1].argv == ["nixos-generate-config", "--root", "/mnt"]
    assert plan.install_commands[0].argv[0] == "nixos-install"
