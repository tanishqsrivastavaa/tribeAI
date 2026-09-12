from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea

from .widgets import CommandMenu


class Composer(TextArea):
    """Multiline prompt editor: Enter sends, Shift+Enter newlines, history + completion."""

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, **kwargs) -> None:
        super().__init__(soft_wrap=True, tab_behavior="indent", **kwargs)
        self.show_line_numbers = False
        self._history: list[str] = []
        self._hpos: int | None = None
        self._draft = ""
        self.menu: CommandMenu | None = None

    def set_menu(self, menu: CommandMenu | None) -> None:
        self.menu = menu

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, text: str) -> None:
        self.load_text(text)

    def _replace_all(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    def _at_top(self) -> bool:
        return self.cursor_location[0] == 0

    def _at_bottom(self) -> bool:
        return self.cursor_location[0] == self.document.line_count - 1

    async def _on_key(self, event: events.Key) -> None:
        menu = self.menu
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self._submit()
            return
        if event.key in ("shift+enter", "alt+enter", "ctrl+j"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        if event.key == "escape" and menu is not None and menu.active:
            event.prevent_default()
            event.stop()
            menu.update_query("")
            return
        if event.key == "tab" and menu is not None and menu.active:
            event.prevent_default()
            event.stop()
            self._accept_completion()
            return
        if event.key == "up":
            if menu is not None and menu.active:
                event.prevent_default()
                event.stop()
                menu.move(-1)
                return
            if self._at_top():
                event.prevent_default()
                event.stop()
                self._history_prev()
                return
        if event.key == "down":
            if menu is not None and menu.active:
                event.prevent_default()
                event.stop()
                menu.move(1)
                return
            if self._at_bottom():
                event.prevent_default()
                event.stop()
                self._history_next()
                return
        await super()._on_key(event)

    def _accept_completion(self) -> None:
        if self.menu is None:
            return
        name = self.menu.selected()
        if name:
            self._replace_all(name + " ")
            self.menu.update_query("")

    def _submit(self) -> None:
        value = self.text.strip()
        if not value:
            return
        if not self._history or self._history[-1] != value:
            self._history.append(value)
        self._hpos = None
        self._draft = ""
        self.load_text("")
        self.post_message(self.Submitted(value))

    def _history_prev(self) -> None:
        if not self._history:
            return
        if self._hpos is None:
            self._draft = self.text
            self._hpos = len(self._history)
        if self._hpos > 0:
            self._hpos -= 1
            self._replace_all(self._history[self._hpos])

    def _history_next(self) -> None:
        if self._hpos is None:
            return
        self._hpos += 1
        if self._hpos >= len(self._history):
            self._hpos = None
            self._replace_all(self._draft)
        else:
            self._replace_all(self._history[self._hpos])
