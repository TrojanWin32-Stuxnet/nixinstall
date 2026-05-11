import json

from nixosinstall.models import DesktopProfile, DiskBackend, InstallConfig, NixMode, ServerProfile


def test_config_round_trip(tmp_path):
    config = InstallConfig.default()
    config.network.host_name = "workstation"
    config.disk.backend = DiskBackend.IMPERATIVE
    config.nix.mode = NixMode.CLASSIC
    config.desktop = DesktopProfile.GNOME
    config.servers = [ServerProfile.SSH]
    config.packages = ["git", "vim"]

    path = tmp_path / "user_configuration.json"
    config.save(path)

    loaded = InstallConfig.load(path)

    assert loaded.network.host_name == "workstation"
    assert loaded.disk.backend == DiskBackend.IMPERATIVE
    assert loaded.nix.mode == NixMode.CLASSIC
    assert loaded.desktop == DesktopProfile.GNOME
    assert loaded.servers == [ServerProfile.SSH]
    assert loaded.packages == ["git", "vim"]


def test_load_defaults_from_partial_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"network": {"host_name": "mini"}}))

    loaded = InstallConfig.load(path)

    assert loaded.network.host_name == "mini"
    assert loaded.disk.backend == DiskBackend.DISKO
    assert loaded.nix.mode == NixMode.BOTH
