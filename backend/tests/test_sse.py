from app.schemas import ExpertTokenEvent
from app.sse import format_sse


def test_format_sse_ends_with_double_newline():
    evt = ExpertTokenEvent(round=0, expert_id="claude", delta="hello")
    frame = format_sse(evt)
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")


def test_format_sse_contains_valid_json():
    import json
    evt = ExpertTokenEvent(round=0, expert_id="claude", delta="테스트")
    frame = format_sse(evt)
    payload = frame[len("data: "):].strip()
    data = json.loads(payload)
    assert data["type"] == "expert_token"
    assert data["delta"] == "테스트"
