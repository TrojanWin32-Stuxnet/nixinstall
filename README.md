# nixosinstall

`nixosinstall` is a greenfield guided installer prototype for NixOS. It is
inspired by archinstall's flow, but renders NixOS configuration and plans
NixOS-native install commands.

The first milestone supports:

- JSON configuration loading and saving
- classic and flake NixOS output
- disko-first disk preparation
- imperative disk backend command planning
- dry-run command and file previews
- a minimal Textual guided menu

Preview the generated files and install commands:

```shell
python -m nixosinstall --dry-run --silent
```

Run a real install from a NixOS installer environment after reviewing the
plan:

```shell
python -m nixosinstall --silent --yes --config ./user_configuration.json
```

Without `--yes`, the installer prints the full plan and asks for a typed
confirmation before running destructive disk commands.

The non-dry-run flow is:

1. Write the temporary disko config, when using the disko backend.
2. Partition, format, and mount the target system.
3. Run `nixos-generate-config --root /mnt` for hardware configuration.
4. Write the generated NixOS config files to `/mnt/etc/nixos`.
5. Run `nixos-install`.
