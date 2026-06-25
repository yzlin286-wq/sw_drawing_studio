from app.services.run_manager import full_pipeline
from pathlib import Path

case_dir = Path(r'c:\Users\Vision\Desktop\SW 相关\3D转2D测试图纸')
files = sorted([f for f in case_dir.glob('LB26001-A-04-00*.SLDPRT') if not f.name.startswith('~$')])
print(f'Found {len(files)} files:')
for f in files:
    print(f'  {f.name}')
results = []
for i, f in enumerate(files, 1):
    print(f'\n=== {i}/{len(files)} {f.name} ===')
    try:
        ctx = full_pipeline(str(f), 'v6_recommended')
        status = 'success' if not ctx.hard_fail and not ctx.warnings else ('warning' if not ctx.hard_fail else 'failed')
        results.append({'base': f.stem, 'status': status, 'hard_fail': list(ctx.hard_fail or []), 'qc_pass': ctx.qc_pass_count, 'dim_total': ctx.dim_total, 'drawing_usable': ctx.drawing_usable.get('pass') if isinstance(ctx.drawing_usable, dict) else False})
        print(f'  status={status} hard_fail={ctx.hard_fail} qc_pass={ctx.qc_pass_count} dim={ctx.dim_total} usable={ctx.drawing_usable}')
    except Exception as e:
        results.append({'base': f.stem, 'status': 'failed', 'hard_fail': [str(e)], 'qc_pass': 0, 'dim_total': 0, 'drawing_usable': False})
        print(f'  ERROR: {e}')

print('\n=== SUMMARY ===')
success = sum(1 for r in results if r['status'] == 'success')
warning = sum(1 for r in results if r['status'] == 'warning')
failed = sum(1 for r in results if r['status'] == 'failed')
print(f'total={len(results)} success={success} warning={warning} failed={failed}')
print(f'pass_rate={(success+warning)/len(results)*100:.1f}%')
for r in results:
    print(f"  {r['base']}: {r['status']} hard_fail={r['hard_fail']} qc={r['qc_pass']} dim={r['dim_total']}")
