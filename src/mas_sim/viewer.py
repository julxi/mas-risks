"""Self-contained HTML viewer for mas_sim JSONL logs (record format: logs.py).

build_viewer_html embeds every record of a log into one copy of viewer_template.html,
so the page opens from disk with no server or network. The page shows the runs, each
run's calls as a strip of steps, each agent's exact context (split into collapsible
sections), its reply, and who sees whose output; two runs can be compared side by side.
Written by scripts/view_runs.py.
"""

import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).with_name("viewer_template.html")
DATA_PLACEHOLDER = "/*__MAS_SIM_DATA__*/"
RECORD_TYPES = ("call", "env", "run")


def embed_json(obj: object) -> str:
    """JSON that is safe inside an HTML <script> element.

    An agent reply containing "</script>" or "<!--" would otherwise end the element
    early. "<" can only occur inside JSON strings, where the escape \\u003c means the
    same character, so replacing every "<" keeps the JSON valid and identical in value.
    """
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def build_viewer_html(records: list[dict], source_name: str, pins: list[str] | None = None) -> str:
    """The viewer page with `records` embedded.

    source_name: shown in the page header; also keys the pinned fields the page stores
        in the browser's localStorage.
    pins: outcome fields shown under each run in the run list until the user changes
        the selection in the page.
    """
    assert records, "no records to show"
    for i, r in enumerate(records):
        assert isinstance(r, dict), f"record {i} is {type(r)}, not dict"
        assert r["type"] in RECORD_TYPES, f"record {i}: unknown type {r['type']!r}"
        assert isinstance(r["run_id"], str), f"record {i}: run_id {r['run_id']!r}"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert template.count(DATA_PLACEHOLDER) == 1, f"{TEMPLATE_PATH} must contain {DATA_PLACEHOLDER} exactly once"
    payload = {"source": source_name, "records": records, "pins": list(pins or [])}
    return template.replace(DATA_PLACEHOLDER, embed_json(payload))
