import json
from app.services.health_check import run_health_check
r = run_health_check()
print(f"total={r['total']} pass={r['pass']} warn={r['warning']} fail={r['fail']}")
print("--- v2.1 new checks ---")
for it in r["items"][-4:]:
    print(f"  {it['key']}: {it['status']} - {it['msg']}")
