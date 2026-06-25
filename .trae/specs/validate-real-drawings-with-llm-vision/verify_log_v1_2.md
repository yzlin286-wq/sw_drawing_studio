# v1.2 LLM 真实连通验证日志

## 1. 配置
- provider: ccagent
- base_url: https://api.ccagent.cn/v1
- model: glm-5.1
- vision_model: doubao-seed-2.0-pro
- api_key 末 4 位: bOT

## 2. test_connection
- ok: True
- msg: ok: pong
- latency_ms: 1121

## 3. chat (glm-5.1)
- prompt: 用一句话介绍 SolidWorks
- response: SolidWorks 是一款广泛用于机械设计、产品建模、工程仿真和制造出图的三维 CAD 设计软件。
- latency_ms: 1765

## 4. vision (doubao-seed-2.0-pro)
- image: drw_output/v5/LB26001-A-04-001_v5.PNG
- prompt: 这张工程图包含哪些视图？
- response: 这张工程图包含主视图（展现零件板面结构）、两个侧视图（长度方向、宽度方向侧视的正投影视图），以及用于直观展示零件三维形态的轴测立体视图。
- latency_ms: 44625

## 5. 总结
- 3 条链路是否全部 ok: 是
  - test_connection: ok=True（1121ms）
  - chat: 返回非空文本（1765ms）
  - vision: 返回非空文本（44625ms）
