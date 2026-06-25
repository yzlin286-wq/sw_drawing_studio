# LB26001 修正测试矩阵 v3.0

- 生成时间: `2026-06-22 11:37:26`
- 状态: `ready_for_real_cad_when_solidworks_responds`
- 样本数量: `2`
- pilot: `LB26001-A-04-006`
- 判定: 这是修正测试计划，不是最终真实 CAD 通过证明。

## 前置条件

- SolidWorks 进程必须可响应，且 COM active-object probe 成功。
- 重启或重跑修正测试前，必须先保存所有打开的 SolidWorks 工作。
- 必须通过 JobRuntimeFacade/QProcess worker 执行；UI 线程不得直接调用 SolidWorks COM。
- 必须把 SLDPRT/SLDASM 复制到 run_dir/input_work；不得修改原始测试 CAD 文件。
- 不得降低 QC 阈值，也不得把 Note/OCR/QC sidecar 数值计为真实 DisplayDim。

## 样本矩阵

| 顺序 | 图号 | SLDPRT | 视图规则 | DisplayDim 下限 | 当前状态 | 当前主要差异 | 首个重跑命令 |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | LB26001-A-04-006 | 存在 | 4 视图; 4x2, 7x2 | 12 | fail | display_dim_count_lower_than_reference, generated_all_named_model_views | `python tools\validation\real_cad_smoke_v3.py --part "drw_output\_lb26001_matrix_test\ok\3D转2D测试图纸\LB26001-A-04-006.SLDPRT" --timeout-s 900 --max-rounds 1 --out drw_output\cad_smoke_stylefix_006.json` |
| 2 | LB26001-A-04-008 | 存在 | 2 视图; 4x1, 7x1 | 2 | need_review | view_count_not_equal_reference | `python tools\validation\real_cad_smoke_v3.py --part "drw_output\_lb26001_matrix_test\ok\3D转2D测试图纸\LB26001-A-04-008.SLDPRT" --timeout-s 900 --max-rounds 1 --out drw_output\cad_smoke_stylefix_008.json` |

## 当前差异计数

- `display_dim_count_lower_than_reference`: 1
- `generated_all_named_model_views`: 1
- `view_count_not_equal_reference`: 1

## 六件样本全部通过后的下一步

`python tools\validation\staged_cad_validation_v3.py --set-name LB26001_36 --out-root drw_output\staged_validation`

> 本矩阵只是修正测试计划和离线验收清单；只有 fresh CAD 输出通过上述门槛后，才能作为可交付图纸证明。
