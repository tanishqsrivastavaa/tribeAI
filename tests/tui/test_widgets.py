from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll

from tribe.tui.widgets import (
    CommandMenu,
    StatusBar,
    ToolActivity,
    format_bytes,
    format_duration,
    tool_summary,
)


def test_tool_summary_per_tool():
    assert tool_summary("read", {"path": "a/b.py"}) == "read a/b.py"
    assert tool_summary("write", {"path": "out.txt"}) == "write out.txt"
    assert tool_summary("bash", {"command": "pytest -q"}) == "$ pytest -q"
    assert "grep" in tool_summary("grep", {"pattern": "foo", "path": "src"})


def test_formatting_helpers():
    assert format_duration(0.012) == "12ms"
    assert format_duration(1.5) == "1.5s"
    assert format_bytes(512) == "512 B"
    assert format_bytes(2048) == "2.0 KB"


class _Host(App):
    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="t")
        yield CommandMenu([("/login", "a"), ("/model", "b"), ("/sessions", "c")])
        yield StatusBar()


async def test_tool_activity_lifecycle():
    app = _Host()
    async with app.run_test() as pilot:
        scroll = app.query_one("#t", VerticalScroll)
        tool = ToolActivity("bash", {"command": "ls"})
        await scroll.mount(tool)
        tool.set_awaiting()
        await pilot.pause()
        assert tool.state == "awaiting" and tool.has_class("tool-awaiting")
        tool.set_running()
        await pilot.pause()
        assert tool.state == "running"
        tool.finalize(is_error=False, error=None, output="a\nb\nc", duration=0.02)
        await pilot.pause()
        assert tool.state == "ok" and tool.has_class("tool-ok")
        assert "a\nb\nc" in tool.text_value


async def test_tool_activity_error_auto_expands():
    app = _Host()
    async with app.run_test() as pilot:
        scroll = app.query_one("#t", VerticalScroll)
        tool = ToolActivity("bash", {"command": "boom"})
        await scroll.mount(tool)
        tool.finalize(is_error=True, error="exited with code 1", output="stderr", duration=0.01)
        await pilot.pause()
        assert tool.state == "error"
        assert tool.collapsed is False  # failures expand so they are visible
        assert "exited with code 1" in tool.text_value


async def test_command_menu_filters_and_selects():
    app = _Host()
    async with app.run_test() as pilot:
        menu = app.query_one(CommandMenu)
        menu.update_query("/")
        await pilot.pause()
        assert menu.active and len(menu.matches) == 3
        menu.update_query("/mo")
        await pilot.pause()
        assert menu.active and menu.selected() == "/model"
        menu.update_query("/model ")  # space ends suggestions
        await pilot.pause()
        assert not menu.active
        menu.update_query("hello")  # no leading slash
        await pilot.pause()
        assert not menu.active


async def test_status_bar_context_percent():
    app = _Host()
    async with app.run_test() as pilot:
        bar = app.query_one(StatusBar)
        bar.set(state="working", model="m", est_tokens=300_000, context_limit=1_000_000)
        await pilot.pause()
        assert bar.state == "working"
        rendered = str(bar.render())
        assert "ctx 30%" in rendered
