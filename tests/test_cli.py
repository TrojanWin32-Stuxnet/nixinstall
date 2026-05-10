from pathlib import Path

from nixosinstall.cli import main


def test_cli_dry_run_prints_files_and_commands(capsys):
    rc = main(["--dry-run", "--silent"])

    out = capsys.readouterr().out

    assert rc == 0
    assert "Generated files:" in out
    assert "configuration.nix" in out
    assert "flake.nix" in out
    assert "Planned commands:" in out
    assert "nixos-install" in out


def test_cli_overrides(capsys):
    rc = main(["--dry-run", "--silent", "--disk-backend", "imperative", "--nix-mode", "classic"])

    out = capsys.readouterr().out

    assert rc == 0
    assert "sgdisk" in out
    assert "flake.nix" not in out
    assert "nixos-install --root /mnt" in out


def test_cli_executes_config_generation_before_writing_target_files(monkeypatch, tmp_path):
    calls = []

    def fake_write(files, target_dir):
        calls.append(("write", str(target_dir), [str(file.path) for file in files]))

    def fake_execute(commands):
        calls.append(("execute", [command.description for command in commands]))

    monkeypatch.setattr("nixosinstall.cli.write_generated_files", fake_write)
    monkeypatch.setattr("nixosinstall.cli.execute_commands", fake_execute)

    rc = main(["--silent", "--yes", "--output-dir", str(tmp_path)])

    assert rc == 0
    assert calls[0][0] == "write"
    assert Path(calls[0][1]).parts[-2:] == ("tmp", "nixosinstall")
    assert calls[1] == ("execute", ["Partition, format, and mount target disk with disko"])
    assert calls[2] == ("execute", ["Create NixOS config directory", "Generate hardware-configuration.nix"])
    assert calls[3][0] == "write"
    assert calls[3][1] == str(tmp_path)
    assert calls[4] == ("execute", ["Install NixOS from flake configuration"])
