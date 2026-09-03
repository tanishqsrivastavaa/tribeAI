from tribe.context.estimate import estimate_messages, estimate_tokens
from tribe.sessions import messages


def test_estimate_tokens_roughly_chars_over_four():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_estimate_grows_with_content():
    small = estimate_messages([messages.user("hi")])
    large = estimate_messages([messages.user("x" * 4000)])
    assert large > small


def test_estimate_counts_tool_arguments_and_results():
    call = messages.tool_call("bash", "c1", {"command": "x" * 400})
    result = messages.tool_result("bash", "c1", "y" * 400)
    assert estimate_messages([call]) > 50
    assert estimate_messages([result]) > 50
