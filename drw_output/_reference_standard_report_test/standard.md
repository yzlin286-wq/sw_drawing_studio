# LB26001 参考图纸制图规范 v3.0

- 生成时间: `2026-06-22 11:31:34`
- 状态: `standard_ready`
- 样本数量: `2`
- 判定: 这是规范学习报告，不是最终真实 CAD 通过证明。

## 全局硬规则

- `exact_same_name_view_family` [need_review]: 已学习的 LB26001 同名样本必须匹配参考图纸的视图数量和视图类型计数。
- `projected_views_are_not_named_view_substitutes` [need_review]: 参考图中的 type 4 投影视图必须用真实投影视图生成，不能用独立命名模型视图替代。
- `real_displaydim_floor` [fail]: 生成图纸的真实 SolidWorks DisplayDim 数量不得低于同名参考图纸基线。
- `no_note_or_sidecar_displaydim_substitution` [fail]: Note、OCR 文本、视觉文本和 QC sidecar 数值只能辅助复核，不能计为真实 DisplayDim。
- `reference_layout_center_tolerance` [need_review]: front/top/right/iso 语义视图中心必须保持在参考布局 0.08 归一化图幅单位内。
- `no_extra_section_or_detail_for_six_samples` [need_review]: 六张已学习样本只使用 type 7 和 type 4，同名零件禁用自动新增剖视图/详图。

## 样本规则

| 图号 | 视图数 | 视图类型 | DisplayDim 下限 | 图幅(mm) | 布局槽中心(norm) | 剖视/详图策略 |
| --- | ---: | --- | ---: | --- | --- | --- |
| LB26001-A-04-006 | 4 | 4(投影视图)x2, 7(标准/命名模型视图)x2 | 12 | 297.0 x 210.0 | front=(0.3700,0.8000); iso=(0.8000,0.4800); right=(0.7200,0.8000); top=(0.3700,0.5800) | 禁止自动新增剖视/详图 |
| LB26001-A-04-008 | 2 | 4(投影视图)x1, 7(标准/命名模型视图)x1 | 2 | 297.0 x 210.0 | front=(0.3700,0.8000); top=(0.7200,0.8000) | 禁止自动新增剖视/详图 |

## 当前历史差距

- gap 状态: `fail`, pass=`False`
- 样本: `2`, pass=`0`, need_review=`0`, fail=`2`
- 差异计数:
  - `display_dim_count_lower_than_reference`: 1
  - `view_type_count_lower_than_reference`: 1

## 修正测试顺序

1. 先恢复可响应的 SolidWorks COM active-object 会话，再进行真实修正测试。
2. 通过 JobRuntimeFacade/start_cad_job 重跑 LB26001-A-04-006，并要求视图类型 7x2/4x2、DisplayDim >= 12、无额外视图族、布局通过。
3. 006 通过后，再按各自视图规则和 DisplayDim 下限重跑 007/008/009/015/022。
4. 六张样本全部通过 strict style gate 后，才允许重跑 LB26001_36。

> 本报告只是已学习制图规范和离线证据；只有 fresh SLDDRW/PDF/DXF/PNG 全部通过严格验证后，才能作为真实 CAD 通过证明。
