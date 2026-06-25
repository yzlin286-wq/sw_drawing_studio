import json
d = json.load(open("drw_output/v2_1_validation_result.json", "r", encoding="utf-8"))
print("Top keys:", list(d.keys()))
print("overall_pass:", d.get("overall_pass"))
print()
checks = d.get("checks", {})
print("=== checks ===")
if isinstance(checks, dict):
    for name, status in checks.items():
        print(f"  {name}: {status}")
elif isinstance(checks, list):
    for c in checks:
        print(f"  {c}")
