import sys
import json
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services import build_default_client, vision_score

llm = build_default_client()
print(f"[client] {llm!r}")

ok, msg, lat = llm.test_connection()
print(f"[test_connection] ok={ok} latency_ms={lat}")
print(f"[test_connection.msg] {msg}")

if ok:
    slddrw = r"c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5.SLDDRW"
    qc_json = r"c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5_qc.json"
    try:
        result = vision_score(slddrw, qc_json, llm)
        print("[vision_score]")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"[vision_score.error] {type(e).__name__}: {e}")
else:
    print("[skip] vision_score skipped because LLM not configured / 401")
