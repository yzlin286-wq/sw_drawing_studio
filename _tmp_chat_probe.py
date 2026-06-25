from app.services import build_default_client

c = build_default_client()
r = c.chat([
    {"role": "system", "content": "你是机械制图工程师，遵循 GB/T 4458.4 与 GB/T 1804-m"},
    {"role": "user", "content": "为一钣金件 LB26001-A-04-001 生成 3 条中文技术要求，每条一行，含表面处理与公差。"}
])
print("LATENCY:", r["latency_ms"])
print("TEXT:")
print(r["text"])
