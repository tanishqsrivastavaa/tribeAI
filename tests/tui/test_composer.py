from __future__ import annotations

from textual.app import App, ComposeResult

from tribe.tui.composer import Composer


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Composer(id="c")

    def on_mount(self) -> None:
        self.submitted: list[str] = []
        self.query_one(Composer).focus()

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        self.submitted.append(event.value)


async def test_enter_submits_and_clears():
    app = _Host()
    async with app.run_test() as pilot:
        composer = app.query_one(Composer)
        composer.value = "hello world"
        await pilot.press("enter")
        assert app.submitted == ["hello world"]
        assert composer.text == ""


async def test_blank_enter_does_not_submit():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert app.submitted == []


async def test_ctrl_j_inserts_newline():
    app = _Host()
    async with app.run_test() as pilot:
        composer = app.query_one(Composer)
        composer.value = "line1"
        composer.move_cursor(composer.document.end)
        await pilot.press("ctrl+j")
        await pilot.press(*"line2")
        await pilot.press("enter")
        assert app.submitted == ["line1\nline2"]


async def test_history_recall_with_arrows():
    app = _Host()
    async with app.run_test() as pilot:
        composer = app.query_one(Composer)
        for text in ("first", "second"):
            composer.value = text
            await pilot.press("enter")
        await pilot.press("up")
        assert composer.text == "second"
        await pilot.press("up")
        assert composer.text == "first"
        await pilot.press("down")
        assert composer.text == "second"
        await pilot.press("down")
        assert composer.text == ""
