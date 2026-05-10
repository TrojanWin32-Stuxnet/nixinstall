from __future__ import annotations

from typing import TYPE_CHECKING

from nixosinstall.models import DesktopProfile, InstallConfig, ServerProfile

if TYPE_CHECKING:
    from textual.app import ComposeResult


async def collect_config(initial: InstallConfig) -> InstallConfig:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, Footer, Header, Input, Label, Select, Switch
    except ModuleNotFoundError:
        return initial

    class ConfigApp(App[InstallConfig]):
        CSS = """
        Screen {
            align: center middle;
        }
        #panel {
            width: 80;
            max-width: 100%;
            padding: 1 2;
            border: solid $accent;
        }
        Input, Select {
            width: 100%;
        }
        Horizontal {
            height: auto;
        }
        Button {
            margin-top: 1;
        }
        """

        def __init__(self, config: InstallConfig) -> None:
            super().__init__()
            self.config = config

        def compose(self) -> ComposeResult:
            yield Header()
            with Vertical(id="panel"):
                yield Label("NixOS guided installer")
                yield Label("Hostname")
                yield Input(value=self.config.network.host_name, id="host")
                yield Label("Disk device")
                yield Input(value=self.config.disk.device, id="device")
                yield Label("Desktop profile")
                yield Select(
                    [(item.value, item.value) for item in DesktopProfile],
                    value=self.config.desktop.value,
                    id="desktop",
                )
                yield Label("Enable OpenSSH")
                yield Switch(value=ServerProfile.SSH in self.config.servers, id="ssh")
                with Horizontal():
                    yield Button("Continue", variant="primary", id="continue")
                    yield Button("Cancel", id="cancel")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self.exit(self.config)
                return

            self.config.network.host_name = self.query_one("#host", Input).value or self.config.network.host_name
            self.config.disk.device = self.query_one("#device", Input).value or self.config.disk.device
            desktop = self.query_one("#desktop", Select).value
            if isinstance(desktop, str):
                self.config.desktop = DesktopProfile(desktop)
            ssh = self.query_one("#ssh", Switch).value
            if ssh and ServerProfile.SSH not in self.config.servers:
                self.config.servers.append(ServerProfile.SSH)
            if not ssh and ServerProfile.SSH in self.config.servers:
                self.config.servers.remove(ServerProfile.SSH)
            self.exit(self.config)

    return await ConfigApp(initial).run_async()
