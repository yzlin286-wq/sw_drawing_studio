# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for sw_drawing_studio
# 默认 onefile + windowed 模式
# 如果 onefile 体积过大或 Qt plugin 路径出问题，可回退到 onedir：
#   - 注释掉 EXE(...) 中的 a.binaries / a.zipfiles / a.datas 三行（即移除单文件模式参数）
#   - 取消注释下方 COLLECT(...) 段
# 这样产物为 dist/sw_drawing_studio/sw_drawing_studio.exe

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
datas += [('app/workers/drawing_review_worker.py', 'app/workers')]
datas += [('app/workers/qc_action_worker.py', 'app/workers')]
datas += [('app/workers/llm_action_worker.py', 'app/workers')]
datas += [('app/workers/health_check_worker.py', 'app/workers')]
datas += [('app/workers/solidworks_com_probe_worker.py', 'app/workers')]
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
    'app.services.system_health_service',
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
    # v1.9: CAD Core 重构 (Add-in + DocMgr + PMI)
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
    'app.workers.drawing_review_worker',
    'app.workers.qc_action_worker',
    'app.workers.llm_action_worker',
    'app.workers.health_check_worker',
    'app.workers.solidworks_com_probe_worker',
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
    name='sw_drawing_studio',
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

# === onedir 回退方案（默认禁用）===
# 若需要切换为 onedir，请：
# 1) 将上面 EXE(...) 中的 a.binaries / a.zipfiles / a.datas 移除（仅保留 pyz, a.scripts, [], exclude_binaries=True）
# 2) 取消注释以下 COLLECT 段
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='sw_drawing_studio',
# )
