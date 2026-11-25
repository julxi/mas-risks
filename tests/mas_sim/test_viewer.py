"""The HTML viewer embeds the log losslessly. No browser: the page's JavaScript is
checked by hand (see convos/julian/26-11-24_run_viewer_LOG.md)."""

import json
import re

import pytest

from mas_sim.viewer import DATA_PLACEHOLDER, build_viewer_html

RECORDS = [
    {"type": "call", "run_id": "r0", "round": 0, "step": 0, "agent": "a", "raw": "x </script><!-- <b>", "visible": []},
    {"type": "env", "run_id": "r0", "round": 0, "step": 0, "data": {"k": "ü"}},
    {"type": "run", "run_id": "r0", "status": "ok", "config": {}, "outcome": {"ok": True}, "error": None},
]


def embedded(html: str) -> dict:
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "data script element not found"
    return json.loads(m.group(1))


def test_records_round_trip_through_the_page():
    html = build_viewer_html(RECORDS, "log.jsonl", ["ok"])
    assert DATA_PLACEHOLDER not in html
    assert embedded(html) == {"source": "log.jsonl", "records": RECORDS, "pins": ["ok"]}


def test_script_end_tag_in_a_reply_cannot_close_the_data_element():
    html = build_viewer_html(RECORDS, "log.jsonl")
    data_start = html.index('<script id="data"')
    # The only "</script>" after the data element starts must be its own closing tag
    # and the main script's: the reply's "</script>" must have been escaped.
    assert html.count("</script>", data_start) == 2


@pytest.mark.parametrize("bad", [[], [{"type": "nope", "run_id": "r"}], [{"type": "call"}]])
def test_bad_records_rejected(bad):
    with pytest.raises((AssertionError, KeyError)):
        build_viewer_html(bad, "x")
