"""서버 SSE 스트림 수동 테스트 스크립트.

사용법:
  python test_server.py
  python test_server.py "다른 질문을 입력하세요"
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request

# Windows 콘솔 UTF-8 출력 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


QUESTION = sys.argv[1] if len(sys.argv) > 1 else "인공지능이 인간의 창의성을 대체할 수 있을까요?"
URL = "http://localhost:8003/api/debate"

payload = json.dumps({"question": QUESTION}).encode("utf-8")
req = urllib.request.Request(
    URL,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)

print(f"질문: {QUESTION}\n{'='*60}")

with urllib.request.urlopen(req, timeout=300) as resp:
    for raw_line in resp:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        data = json.loads(line[5:].strip())
        etype = data.get("type", "")

        if etype == "debate_start":
            experts = data["experts"]
            print(f"\n[시작] 전문가 {len(experts)}명:")
            for e in experts:
                print(f"  - {e['name']} ({e['provider']}/{e['model']})")

        elif etype == "round_start":
            print(f"\n── 라운드 {data['round']} [{data['stage']}] ──")

        elif etype == "expert_token":
            print(data["delta"], end="", flush=True)

        elif etype == "expert_done":
            print(f"\n  [{data['expert_id']} 완료 · {data['tokens']} tokens]")

        elif etype == "judge_token":
            print(data["delta"], end="", flush=True)

        elif etype == "judge_verdict":
            v = data
            print(f"\n\n{'='*60}")
            print(f"[Judge 판정]")
            print(f"  합의 수준: {v['consensus_level']}%")
            if v.get("dismissed_experts"):
                print(f"  탈락: {v['dismissed_experts']}")
            print(f"\n  최종 답변:\n{v['final_answer']}")
            print(f"\n  근거:\n{v['reasoning']}")

        elif etype == "debate_end":
            print(f"\n{'='*60}")
            print(f"[완료] 총 토큰: {data['total_tokens']} · 소요: {data['duration_ms']}ms")

        elif etype == "error":
            print(f"\n[오류] {data['code']}: {data['message']}")
            break
