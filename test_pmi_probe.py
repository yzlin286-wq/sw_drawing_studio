"""v1.9 Task 5: PMI Probe 批量测试"""
import sys, json, time
sys.path.insert(0, '.')
import win32com.client as wc
from pathlib import Path
from app.services.pmi_probe_service import probe_pmi

sw = wc.GetActiveObject('SldWorks.Application')

core_12 = [
    'LB26001-A-04-001', 'LB26001-A-04-002', 'LB26001-A-04-003',
    'LB26001-A-04-004', 'LB26001-A-04-005', 'LB26001-A-04-007',
    'LB26001-A-04-009',
    '-M3x8十字螺丝-1-V3-V02', '-弹簧压棒弹簧-1-V3-V02',
    '-AK-15-AC-25-1-V3-V02', '-AK-15-AC-26-1-V3-V02', '-AK-15-AC-27-1-V3-V02',
]

results = {
    'version': 'v1.9',
    'task': 'Task 5 MBD/PMI Probe',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'targets': [],
    'summary': {
        'total': len(core_12),
        'success': 0,
        'pmi_available': 0,
        'dimxpert_available': 0,
        'annotation_views_found': 0,
    },
}

test_dir = Path('3D转2D测试图纸')

for base in core_12:
    part_path = test_dir / (base + '.SLDPRT')
    if not part_path.exists():
        results['targets'].append({
            'base': base,
            'success': False,
            'reason': '文件缺失: ' + str(part_path),
        })
        continue

    sw.CloseAllDocuments(True)
    time.sleep(1)

    result = probe_pmi(str(part_path))
    result['base'] = base
    results['targets'].append(result)

    if result.get('success'):
        results['summary']['success'] += 1
    if result.get('pmi_available'):
        results['summary']['pmi_available'] += 1
    if result.get('dimxpert_available'):
        results['summary']['dimxpert_available'] += 1
    if result.get('annotation_view_count', 0) > 0:
        results['summary']['annotation_views_found'] += 1

    pmi = result.get('pmi_available')
    dx = result.get('dimxpert_available')
    av = result.get('annotation_view_count', 0)
    print(base + ': pmi=' + str(pmi) + ', dimxpert=' + str(dx) + ', anno_views=' + str(av))

out_path = Path('drw_output/v1_9_pmi/pmi_probe.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print('\nSummary: ' + json.dumps(results['summary'], ensure_ascii=False))
print('Written to: ' + str(out_path))
