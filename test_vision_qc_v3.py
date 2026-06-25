"""v2.0 Vision QC v3 测试脚本"""
import json
from pathlib import Path
from app.services.vision_qc_v3 import run_vision_qc_v3

# 找一个有 PNG 的 run
run_dir = Path('drw_output/runs/8823efa974a9')
png_path = run_dir / 'drawing' / 'LB26001-A-04-001_v5_vision_ref.png'
manifest_path = run_dir / 'manifest.json'

print(f'PNG exists: {png_path.exists()}')
print(f'Manifest exists: {manifest_path.exists()}')

if png_path.exists():
    # 运行 Vision QC v3（无 PDF，仅 PNG）
    result = run_vision_qc_v3(
        pdf_path=None,
        png_path=str(png_path),
        qc_json_path=None,
        run_dir=run_dir,
        run_id='v2_test',
    )
    # 打印除 steps 外的结果
    output = {k: v for k, v in result.items() if k != 'steps'}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print('--- steps summary ---')
    for k, v in result.get('steps', {}).items():
        if isinstance(v, dict):
            success = v.get('success', 'N/A')
            reason = v.get('reason', '')[:80]
            print(f'  {k}: success={success}, reason={reason}')
