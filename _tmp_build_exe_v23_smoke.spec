# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for sw_drawing_studio
# 榛樿 onefile + windowed 妯″紡
# 濡傛灉 onefile 浣撶Н杩囧ぇ鎴?Qt plugin 璺緞鍑洪棶棰橈紝鍙洖閫€鍒?onedir锛?#   - 娉ㄩ噴鎺?EXE(...) 涓殑 a.binaries / a.zipfiles / a.datas 涓夎锛堝嵆绉婚櫎鍗曟枃浠舵ā寮忓弬鏁帮級
#   - 鍙栨秷娉ㄩ噴涓嬫柟 COLLECT(...) 娈?# 杩欐牱浜х墿涓?dist/sw_drawing_studio/sw_drawing_studio.exe

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = []
datas += [('config/llm.yaml.example', 'config')]
datas += [('config/app.yaml.example', 'config')]
datas += [('config/docmgr.yaml', 'config')]
datas += [('config/drawing_blueprints.yaml', 'config')]
datas += collect_data_files('qt_material')
datas += [('libs/standard_parts/parts.yaml', 'libs/standard_parts')]
datas += [('libs/standard_parts.db', 'libs')]
datas += [('libs/process/process.db', 'libs/process')]
datas += [('libs/pricing/rules.yaml', 'libs/pricing')]
datas += [('libs/research_notes.md', 'libs')]
datas += [('templates/gb_a4_landscape.DRWDOT', 'templates')]
datas += [('templates/macros/auto_section.bas', 'templates/macros')]
datas += [('templates/macros/auto_annotate.bas', 'templates/macros')]
datas += [('templates/macros/build_swp.py', 'templates/macros')]
datas += [('templates/macros/precompile_swp.py', 'templates/macros')]
datas += [('templates/build_drwdot.py', 'templates')]
datas += [('templates/probe_drwdot.py', 'templates')]
datas += [('app/workers/cad_job_worker.py', 'app/workers')]
datas += [('app/workers/batch_job_worker.py', 'app/workers')]
datas += [('app/workers/vision_audit_worker.py', 'app/workers')]
datas += [('app/workers/mock_long_job_worker.py', 'app/workers')]
datas += [('.trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py', '.trae/specs/build-v6-and-validate-exe-ui')]
datas += [('.trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py', '.trae/specs/build-v6-and-validate-exe-ui')]
datas += [('.trae/specs/enforce-drawing-quality/drw_qc_loop.py', '.trae/specs/enforce-drawing-quality')]
datas += [('.trae/specs/enforce-drawing-quality/drw_generate_v5.py', '.trae/specs/enforce-drawing-quality')]
datas += [('.trae/specs/enforce-drawing-quality/drw_quality_check.py', '.trae/specs/enforce-drawing-quality')]
datas += [('.trae/specs/enforce-drawing-quality/gb_drawing_rules.md', '.trae/specs/enforce-drawing-quality')]
datas += [('.trae/specs/enforce-drawing-quality/sw_api_drawing_rules.md', '.trae/specs/enforce-drawing-quality')]
datas += [('.trae/specs/repair-section-and-recompare/section_helper.py', '.trae/specs/repair-section-and-recompare')]
datas += [('.trae/specs/repair-section-and-recompare/drawing_standard_v2.md', '.trae/specs/repair-section-and-recompare')]
datas += [('.trae/specs/repair-section-and-recompare/auto_section.bas', '.trae/specs/repair-section-and-recompare')]

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'qt_material',
    'fitz',
    'httpx',
    'yaml',
    'win32com.client',
    'openpyxl',
    'libs.standard_parts',
    'libs.process',
    'libs.pricing',
    'libs.bom',
    'app.ui.bom_pricing_page',
    'app.ui.single_part_page',
    'app.ui.home_page',
    'app.ui.batch_page',
    'app.ui.qc_page',
    'app.ui.settings_dialog',
    'app.ui.log_panel',
    'app.services.bom_service',
    'app.services.pricing_service',
    'app.services.health_check',
    'app.services.run_manager',
    'app.services.diagnostics',
    'app.services.refdoc_relink_service',
    'app.services.vision_qc',
    'app.services.sw_runner',
    'app.services.llm_client',
    # v1.7
    'app.services.part_classification_service',
    'app.services.dimension_sidecar_service',
    'app.services.standard_part_annotation',
    'app.services.model_dim_seed_service',
    'app.services.persisted_layout_solver',
    'app.services.annotate_sidecar_service',
    'app.services.titlebar_filler',
    'app.services.scale_advisor',
    # v1.8
    'app.services.drawing_accuracy_score',
    'app.services.vision_qc_v2',
    'app.services.final_quality',
    # v1.9: CAD Core 閲嶆瀯 (Add-in + DocMgr + PMI)
    'app.services.sw_addin_client',
    'app.services.sw_docmgr_relink',
    'app.services.pmi_probe_service',
    # v2.0: Add-in Dimension Engine + DocMgr Probe + Vision QC v3
    'app.services.docmgr_service',
    'app.services.pdf_render_service',
    'app.services.ocr_qc_service',
    'app.services.template_symbol_detector',
    'app.services.yolo_drawing_detector',
    'app.services.llm_visual_reviewer',
    'app.services.vision_qc_v3',
    'app.ui.drawing_review_workbench',
    # v2.1: PMI Seed + Blueprint Decision + UI Review Loop
    'app.services.pmi_seed_service',
    'app.services.blueprint_decision_service',
    # v2.2/v2.3: process isolation, session stability, visual audit
    'app.services.job_event_bus',
    'app.services.job_queue',
    'app.services.job_runner',
    'app.services.job_runtime_facade',
    'app.services.resource_paths',
    'app.services.generated_output_scanner',
    'app.services.visual_audit_service',
    'app.services.visual_audit_reporter',
    'app.services.vision_qc_v4',
    'app.services.vision_qc_v5',
    'app.services.vision_evidence_fusion',
    'app.services.vision_false_positive_filter',
    'app.services.vision_issue_tracker',
    'app.services.sw_watchdog',
    'app.services.sw_recovery_policy',
    'app.services.sw_session_supervisor',
    'app.services.sw_dialog_guard',
    'app.services.dialog_guard',
    'app.services.dimension_arrange_service',
    'app.services.layout_solver_v2',
    'app.ui.job_queue_page',
    'app.ui.system_health_page',
    'app.ui.visual_audit_page',
    'app.ui.logs_diagnostics_page',
    'app.ui.titlebar_dialog',
    'app.workers.cad_job_worker',
    'app.workers.batch_job_worker',
    'app.workers.vision_audit_worker',
    'app.workers.mock_long_job_worker',
]

excludes = [
    'tkinter',
    'test',
    'unittest',
]

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='sw_drawing_studio_v23_smoke',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# === onedir 鍥為€€鏂规锛堥粯璁ょ鐢級===
# 鑻ラ渶瑕佸垏鎹负 onedir锛岃锛?# 1) 灏嗕笂闈?EXE(...) 涓殑 a.binaries / a.zipfiles / a.datas 绉婚櫎锛堜粎淇濈暀 pyz, a.scripts, [], exclude_binaries=True锛?# 2) 鍙栨秷娉ㄩ噴浠ヤ笅 COLLECT 娈?# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='sw_drawing_studio_v23_smoke',
# )

