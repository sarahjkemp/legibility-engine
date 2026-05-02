import asyncio

from legibility_engine.app import dashboard


def test_dashboard_contains_valid_split_regex_literal() -> None:
    html = asyncio.run(dashboard())
    assert ".split(/[\\n,]/)" in html
    assert ".split(/[\n,]/)" not in html.replace("\\n", "")
