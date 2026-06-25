# Release Log — v1.0 真实闭环验证

- 验证日期: 2026-06-18
- 测试零件: `3D转2D测试图纸\LB26001-A-04-001.SLDPRT`
- SW 连接: pid=23868, rev=33.5.0
- v6 闭环退出码: 0（1/3 轮命中收敛，final_pass=True）
- qc.json: `c:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-001_v5_qc.json`

---

## 节 A — QC 双轨字段

源文件: [drw_quality_check.py](file:///c:/Users/Vision/Desktop/SW%20相关/.trae/specs/enforce-drawing-quality/drw_quality_check.py)

| 项 | 位置 | 说明 |
| --- | --- | --- |
| `classify_refdoc_status(ref_path, expected_part)` | L225–L242 | refdoc 三分支分类（ok / warning / warning），全部为 severity=warning，不再阻断 |
| `_check_refdoc_correct` 输出 `severity` | L278–L290（severity 字面值在 L280） | 显式输出 `"severity": "warning"` + `reason` |
| `quality_check()` 顶层 `hard_fail` | L989, L1034 | 9 类硬失败：opendoc6_failed / slddrw_missing / pdf_missing / dxf_missing / view_overlap / view_in_frame / dim_total<5 / qc_pass<10/12 / vision_score<60 |
| `quality_check()` 顶层 `warnings` | L990, L1017–L1020, L1035 | 5 个可降级项：refdoc_correct / has_datum_a / has_ra_note / gb_titlebar_complete / gb_has_section_view_or_skipped |
| `quality_check()` 顶层 `drawing_usable` | L1022–L1032, L1036 | 6 个交付准则：files_exported / view_in_frame / view_overlap_ok / dim_total / qc_pass_count / vision_score |

### 实测 qc.json 三字段值（2026-06-18 闭环结果）

```json
{
  "hard_fail": [],
  "warnings": [
    "refdoc_correct",
    "has_datum_a",
    "has_ra_note",
    "gb_titlebar_complete",
    "gb_has_section_view_or_skipped"
  ],
  "drawing_usable": {
    "pass": true,
    "criteria": {
      "files_exported": true,
      "view_in_frame": true,
      "view_overlap_ok": true,
      "dim_total": 44,
      "qc_pass_count": 11,
      "vision_score": null
    }
  }
}
```

- `score_pass_count`: 11/12（与历史不退化）
- `vision_score` 未写入 qc.json（属于异步视觉链路），由 `_tmp_vision_probe.py` 单独探针拿到 = **65/100**

---

## 节 B — 环境自检

源文件: [health_check.py](file:///c:/Users/Vision/Desktop/SW%20相关/app/services/health_check.py)

`run_health_check()` 实测 7 项结果（2026-06-18 16:31:08）：

| 项 | ok | msg |
| --- | --- | --- |
| sw         | ✅ | 已连接 (rev=33.5.0) |
| template   | ✅ | gb_a4_landscape.DRWDOT (76.3 KB) |
| macro      | ✅ | auto_section.bas 就绪 (.swp 待手动编译) |
| output_dir | ✅ | C:\Users\Vision\Desktop\SW 相关\drw_output |
| llm        | ✅ | 配置就绪: glm-5.1 |
| db         | ✅ | 标准件/工艺/报价 数据就绪 |
| generator  | ✅ | v6 + v5 出图脚本均就绪 |

- summary.pass = **7 / 7**
- summary.all_ok = **True**

---

## 节 C — UI 分层

| 文件 | 位置 | 改动 |
| --- | --- | --- |
| [home_page.py](file:///c:/Users/Vision/Desktop/SW%20相关/app/ui/home_page.py#L17-L192) | L17 import、L80–L93 健康卡构造、L116 启动触发、L159–L192 `_refresh_health()` | 首页「环境自检」状态卡：badge + name + msg + summary |
| [qc_page.py](file:///c:/Users/Vision/Desktop/SW%20相关/app/ui/qc_page.py#L49-L89) | L49–L58 status_strip 5 标签构造、L79 加入主布局、L82–L89 `update_status_strip()` | qc 页顶部 5 项分层状态条：出图 / 质量 / 视觉 / 可交付 / 警告 |
| [batch_page.py](file:///c:/Users/Vision/Desktop/SW%20相关/app/ui/batch_page.py#L24-L230) | L24 "状态"列、L29 "状态(汇总)"列、L90 表头、L177–L191 `update_row()` + 颜色、L223–L230 `update_row_status()` | batch 页 状态(汇总) 列：success/warning/fail + tooltip |
| [main_window.py](file:///c:/Users/Vision/Desktop/SW%20相关/app/ui/main_window.py#L207-L222) | L208 QLabel、L209–L213 QComboBox 3 项、L215–L222 `_on_strategy_changed()` | 工具栏「出图策略」下拉框：v6 推荐 / v5 兼容 / v6 调试；v5 设 USE_V5=1 |

首页环境自检卡截图: [01_home_health.png](file:///c:/Users/Vision/Desktop/SW%20相关/.trae/specs/release-v1-degrade-refdoc-warning/screenshots/01_home_health.png)

---

## 节 D — 阶段对比 + v1.0 发布判定

| 阶段 | vision_score | qc_pass | refdoc 视为 | drawing_usable |
| --- | --- | --- | --- | --- |
| build-v6 Task 7    | 65 | 11/12 | hard_fail | N/A |
| fix-refdoc Task 5  | 65 | 11/12 | hard_fail | N/A |
| **release-v1 Task 5** | **65** | **11/12** | **warning** | **True** |

### v1.0 发布判定: **PASS**

```
v1.0 发布判定: PASS
- drawing_usable.pass = True
- hard_fail = []
- warnings = ["refdoc_correct", "has_datum_a", "has_ra_note", "gb_titlebar_complete", "gb_has_section_view_or_skipped"]
- 判定理由: 当 hard_fail=[] 且 drawing_usable.pass=True 时，PASS
```

注：refdoc 已按 spec 降级为 warning，不再阻断；qc_pass=11/12、vision_score=65 均未退化；交付文件 SLDDRW/PDF/DXF 三件齐全（v5 后缀产物在 `drw_output/v5/`）。
