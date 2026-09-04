from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from ..models import PROVIDERS


class ProviderSelectScreen(ModalScreen[str | None]):
    """Step 1: pick a model provider from the registry."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Select a model provider", id="login-title")
            yield Static("↑/↓ to move, enter to select, esc to cancel", id="login-hint")
            options = []
            for name in sorted(PROVIDERS):
                provider = PROVIDERS[name]
                configured = provider.api_key_env and os.environ.get(provider.api_key_env)
                marker = "✓" if configured else " "
                options.append(Option(f"{marker} {name}  ({provider.api_key_env})", id=name))
            yield OptionList(*options, id="provider-list")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ApiKeyScreen(ModalScreen[str | None]):
    """Step 2: enter (or keep) the API key for the chosen provider."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, provider: str) -> None:
        super().__init__()
        self.provider = provider
        self.env_var = PROVIDERS[provider].api_key_env or ""
        self.existing = bool(self.env_var and os.environ.get(self.env_var))

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static(f"Enter your {self.provider} API key", id="login-title")
            hint = f"Kept in ${self.env_var} for this session only."
            if self.existing:
                hint += " A key is already set — leave blank to keep it."
            yield Static(hint, id="login-hint")
            yield Input(placeholder=self.env_var, password=True, id="key-input")
            yield Label("", id="login-error")

    def on_mount(self) -> None:
        self.query_one("#key-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if not value and not self.existing:
            self.query_one("#login-error", Label).update("A key is required.")
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ModelSelectScreen(ModalScreen[str | None]):
    """Step 3: type the model name to use (defaults to the provider's default)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, provider: str, current: str | None = None) -> None:
        super().__init__()
        self.provider = provider
        self.default_model = PROVIDERS[provider].default_model
        self.initial = current or self.default_model

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static(f"Choose a model for {self.provider}", id="login-title")
            yield Static(f"Default: {self.default_model}", id="login-hint")
            yield Input(value=self.initial, id="model-input")

    def on_mount(self) -> None:
        model_input = self.query_one("#model-input", Input)
        model_input.focus()
        model_input.cursor_position = len(model_input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value.strip() or self.initial)

    def action_cancel(self) -> None:
        self.dismiss(None)
