from nixosinstall.models import (
    DesktopProfile,
    DiskBackend,
    EncryptionMode,
    Filesystem,
    InstallConfig,
    NetworkMode,
    NixMode,
    ServerProfile,
)
from nixosinstall.nix import NixConfigRenderer


def test_render_both_modes_outputs_expected_files():
    config = InstallConfig.default()
    config.network.host_name = "nixbox"

    files = NixConfigRenderer().render(config)
    names = {str(file.path) for file in files}

    assert names == {"configuration.nix", "flake.nix", "system.nix", "disko-config.nix"}


def test_render_classic_only_omits_flake():
    config = InstallConfig.default()
    config.nix.mode = NixMode.CLASSIC

    names = {str(file.path) for file in NixConfigRenderer().render(config)}

    assert "configuration.nix" in names
    assert "flake.nix" not in names
    assert "system.nix" not in names


def test_render_gnome_ssh_profile():
    config = InstallConfig.default()
    config.desktop = DesktopProfile.GNOME
    config.servers = [ServerProfile.SSH]

    rendered = NixConfigRenderer().render_configuration(config)

    assert "services.xserver.desktopManager.gnome.enable = true;" in rendered
    assert "services.openssh.enable = true;" in rendered


def test_render_btrfs_luks_disko():
    config = InstallConfig.default()
    config.disk.filesystem = Filesystem.BTRFS
    config.disk.encryption = EncryptionMode.LUKS

    rendered = NixConfigRenderer().render_disko(config)

    assert 'type = "luks";' in rendered
    assert 'format = "btrfs";' in rendered
    assert 'mountOptions = [ "compress=zstd" "noatime" ];' in rendered


def test_flake_with_disko_imports_disko_module():
    config = InstallConfig.default()

    rendered = NixConfigRenderer().render_flake(config)

    assert 'disko.url = "github:nix-community/disko";' in rendered
    assert "modules = [ disko.nixosModules.disko ./system.nix ];" in rendered


def test_classic_configuration_does_not_import_disko_options():
    config = InstallConfig.default()

    rendered = NixConfigRenderer().render_configuration(config)

    assert "./disko-config.nix" not in rendered


def test_disko_swap_partition_is_before_root_partition():
    config = InstallConfig.default()
    config.disk.swap_size = "8G"

    rendered = NixConfigRenderer().render_disko(config)

    assert 'swap = {' in rendered
    assert rendered.index("swap = {") < rendered.index("root = {")


def test_imperative_flake_omits_disko_input():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE

    rendered = NixConfigRenderer().render_flake(config)

    assert "disko.url" not in rendered
    assert "modules = [ ./system.nix ];" in rendered


def test_dynamic_nix_attribute_names_are_quoted():
    config = InstallConfig.default()
    config.network.host_name = "nix-box"
    config.network.interface = "enp0s1-lab"
    config.network.mode = NetworkMode.MANUAL
    config.network.address = "192.0.2.10/24"
    config.services = ["custom-backup.timer"]
    config.users[0].username = "ops-user"

    flake = NixConfigRenderer().render_flake(config)
    configuration = NixConfigRenderer().render_configuration(config)

    assert 'nixosConfigurations."nix-box"' in flake
    assert 'networking.interfaces."enp0s1-lab".ipv4.addresses' in configuration
    assert 'users.users."ops-user"' in configuration
    assert 'systemd.services."custom-backup.timer".wantedBy' in configuration


def test_imperative_backend_omits_disko_file():
    config = InstallConfig.default()
    config.disk.backend = DiskBackend.IMPERATIVE

    names = {str(file.path) for file in NixConfigRenderer().render(config)}

    assert "disko-config.nix" not in names
