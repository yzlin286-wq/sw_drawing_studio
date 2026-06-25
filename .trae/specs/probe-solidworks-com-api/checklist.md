# Checklist

## 官方文档抽取
- [x] `sw_com_api_index.md` 已创建
- [x] 覆盖 14 个核心分组
- [x] 每分组 ≥10 个方法/属性
- [x] 每条含官方签名 + Help URL 锚点

## 探针脚本
- [x] `probe_runner.py` 已创建
- [x] 支持 `--group` 过滤、`--write` 启用破坏性接口
- [x] SW 未启动时友好降级（returncode=2，stub JSON）
- [x] 默认对 `3D转2D测试图纸/LB26001-A-04-001.SLDPRT` 跑只读探针

## 在线探针运行
- [x] `probe_result.json` 落盘（pass=48 / fail=9 / skip=26 / total=83）
- [x] `probe_log.md` 含 pass/warn/fail 摘要
- [x] 至少 14 个分组都有结果（在线 run 或 SKIP 标注，装配/工程图分组因当前样本是零件而 skip，已在 sw_com_api_probe.md 文档中说明）

## API 文档
- [x] `sw_com_api_probe.md` 已创建
- [x] 每条接口含状态 / 原因 / Python 示例 / 解决方案
- [x] 头部含统计概览

## 不可用清单
- [x] `unresolved_apis.md` 已创建
- [x] 6 类分桶
- [x] 每条 (原因 / 解决方案 / 优先级) 三字段全填

## 全局
- [x] 没有删除任何 spec 文档
- [x] 没有改动 `dist/sw_drawing_studio.exe`、`app/` 与其他 spec 产物
- [x] 所有新文件均位于 `.trae/specs/probe-solidworks-com-api/` 下
