import json
from app.services.health_check import run_health_check
result = run_health_check()
items = result.get("items", [])
print("=== Health Check Items ===")
for i in items:
    status = i.get("status", "")
    name = i.get("name", "")
    msg = i.get("msg", "")
    fix = i.get("fix", "")
    marker = " <<< FAIL" if status == "fail" else (" [WARN]" if status == "warning" else "")
    print(f"  [{status:7s}] {name}: {msg}{marker}")
    if fix and status in ("fail", "warning"):
        print(f"           fix: {fix}")
print(f"\nTotal: {result.get('total')}, Pass: {result.get('pass_count')}, Warn: {result.get('warning_count')}, Fail: {result.get('fail_count')}")
