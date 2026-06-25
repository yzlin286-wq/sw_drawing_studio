import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const drwOutput = path.join(repoRoot, "drw_output");
const defaultOut = path.join(drwOutput, "reference_comparison_report_v3_0.xlsx");

function argValue(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index >= 0 && process.argv[index + 1]) {
    return path.resolve(process.cwd(), process.argv[index + 1]);
  }
  return fallback;
}

function safeJson(text, fallback = {}) {
  try {
    return JSON.parse(text.replace(/^\uFEFF/, ""));
  } catch {
    return fallback;
  }
}

async function readJson(file, fallback = {}) {
  try {
    return safeJson(await fs.readFile(file, "utf8"), fallback);
  } catch {
    return fallback;
  }
}

async function exists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function walk(dir, predicate, out = []) {
  let entries = [];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await walk(full, predicate, out);
    } else if (predicate(full, entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function basenameAny(value) {
  const raw = String(value || "");
  const tail = raw.split(/[\\/]/).filter(Boolean).pop() || raw;
  return tail.replace(/\.(SLDPRT|SLDASM|SLDDRW)$/i, "");
}

function stageInfo(file) {
  const rel = path.relative(drwOutput, file).split(path.sep);
  const idx = rel.indexOf("staged_validation");
  if (idx >= 0 && rel.length >= idx + 4) {
    return {
      sourceType: "staged",
      stage: rel[idx + 1],
      runStamp: rel[idx + 2],
      caseName: rel[idx + 3],
      summaryPath: path.join(drwOutput, ...rel.slice(0, idx + 3), "summary.json"),
    };
  }
  return {
    sourceType: "ad_hoc",
    stage: "ad_hoc",
    runStamp: "",
    caseName: path.basename(path.dirname(file)),
    summaryPath: "",
  };
}

function statusRank(status) {
  const order = { fail: 0, need_review: 1, pass_with_warning: 2, no_reference: 3, pass: 4 };
  return order[String(status || "")] ?? 0;
}

function metricCount(metrics, key) {
  const value = metrics?.[key];
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeDiffs(report, source) {
  return (report?.differences || []).map((diff) => ({
    source,
    key: String(diff?.key || ""),
    severity: String(diff?.severity || ""),
    reference: typeof diff?.reference === "string" ? diff.reference : JSON.stringify(diff?.reference ?? ""),
    generated: typeof diff?.generated === "string" ? diff.generated : JSON.stringify(diff?.generated ?? ""),
    fix: String(diff?.fix_suggestion || ""),
  }));
}

async function loadStyleGapByBase() {
  const reports = await walk(
    path.join(drwOutput, "reference_style_profile"),
    (full, name) => name === "lb26001_reference_style_gap_report.json",
  );
  const map = new Map();
  const rows = [];
  for (const file of reports) {
    const stat = await fs.stat(file);
    const payload = await readJson(file, {});
    for (const item of payload.cases || []) {
      const base = String(item.base || "");
      if (!base) continue;
      const row = {
        base,
        sourceReport: file,
        reportMtime: stat.mtime.toISOString(),
        status: String(item.status || ""),
        pass: Boolean(item.pass),
        overall: Number(item.overall_style_score || 0),
        viewScore: Number(item.view_style_score || 0),
        dimScore: Number(item.dimension_style_score || 0),
        layoutScore: Number(item.layout_style_score || 0),
        reasons: (item.reasons || []).join("; "),
        differences: item.differences || [],
      };
      rows.push(row);
      const prev = map.get(base);
      if (!prev || stat.mtimeMs > prev.mtimeMs) {
        map.set(base, { ...row, mtimeMs: stat.mtimeMs });
      }
    }
  }
  return { map, rows };
}

async function loadStageSummaries() {
  const files = await walk(
    path.join(drwOutput, "staged_validation"),
    (full, name) => name === "summary.json",
  );
  const rows = [];
  for (const file of files) {
    const payload = await readJson(file, {});
    rows.push({
      stage: String(payload.stage || ""),
      generatedAt: String(payload.generated_at || ""),
      status: String(payload.status || ""),
      pass: Boolean(payload.pass),
      total: Number(payload.total || 0),
      processed: Number(payload.processed || 0),
      deliverable: Number(payload.deliverable_count || 0),
      needReview: Number(payload.need_review_count || 0),
      failed: Number(payload.failed_count || 0),
      acceptancePass: Boolean(payload.acceptance_pass ?? payload.pass),
      report: file,
    });
  }
  rows.sort((a, b) => `${a.stage}:${a.generatedAt}`.localeCompare(`${b.stage}:${b.generatedAt}`));
  return rows;
}

async function loadComparisonRows(styleByBase) {
  const files = await walk(drwOutput, (full, name) => name === "reference_compare.json");
  const rows = [];
  const issueRows = [];
  for (const file of files) {
    const report = await readJson(file, {});
    const info = stageInfo(file);
    const partName = basenameAny(report.part || info.caseName);
    const localStylePath = path.join(path.dirname(file), "reference_style.json");
    const localStyle = (await exists(localStylePath)) ? await readJson(localStylePath, {}) : {};
    const fallbackStyle = styleByBase.get(partName) || {};
    const styleStatus = String(localStyle.status || fallbackStyle.status || "");
    const stylePass =
      Object.keys(localStyle).length > 0
        ? Boolean(localStyle.pass)
        : Object.keys(fallbackStyle).length > 0
          ? Boolean(fallbackStyle.pass)
          : "";
    const styleSource =
      Object.keys(localStyle).length > 0
        ? localStylePath
        : Object.keys(fallbackStyle).length > 0
          ? fallbackStyle.sourceReport
          : "";

    const reference = report.reference_metrics || {};
    const generated = report.generated_metrics || {};
    const row = {
      stage: info.stage,
      runStamp: info.runStamp,
      caseName: info.caseName,
      partName,
      status: String(report.status || ""),
      pass: Boolean(report.pass),
      styleStatus,
      stylePass,
      overall: Number(report.overall_score || 0),
      viewScore: Number(report.view_match_score || 0),
      dimensionScore: Number(report.dimension_match_score || 0),
      titlebarScore: Number(report.titlebar_match_score || 0),
      annotationScore: Number(report.annotation_match_score || 0),
      layoutScore: Number(report.layout_match_score || 0),
      refViews: metricCount(reference, "view_count"),
      genViews: metricCount(generated, "view_count"),
      refDims: metricCount(reference, "display_dim_count"),
      genDims: metricCount(generated, "display_dim_count"),
      differenceCount: (report.differences || []).length + (localStyle.differences || fallbackStyle.differences || []).length,
      referenceDrawing: String(report.reference_drawing || ""),
      generatedDrawing: String(report.generated_drawing || ""),
      runDir: String(report.run_dir || ""),
      reportPath: file,
      styleSource,
    };
    rows.push(row);

    for (const diff of normalizeDiffs(report, "reference_compare")) {
      issueRows.push({ stage: row.stage, partName, reportPath: file, ...diff });
    }
    const styleDiffs = normalizeDiffs(
      Object.keys(localStyle).length > 0 ? localStyle : fallbackStyle,
      Object.keys(localStyle).length > 0 ? "reference_style" : "reference_style_gap",
    );
    for (const diff of styleDiffs) {
      issueRows.push({ stage: row.stage, partName, reportPath: styleSource, ...diff });
    }
  }
  rows.sort((a, b) => `${a.stage}:${a.runStamp}:${a.caseName}`.localeCompare(`${b.stage}:${b.runStamp}:${b.caseName}`));
  return { rows, issueRows };
}

function writeRows(sheet, startRow, startCol, rows) {
  if (!rows.length) return;
  sheet.getRangeByIndexes(startRow, startCol, rows.length, rows[0].length).values = rows;
}

function applyHeader(range) {
  range.format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
}

function applyBody(range) {
  range.format = {
    borders: {
      insideHorizontal: { style: "thin", color: "#E5E7EB" },
      top: { style: "thin", color: "#CBD5E1" },
      bottom: { style: "thin", color: "#CBD5E1" },
    },
    verticalAlignment: "top",
    wrapText: true,
  };
}

async function buildWorkbook({ rows, issueRows, stageRows, styleRows, outputPath }) {
  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("总览");
  const stages = workbook.worksheets.add("阶段汇总");
  const details = workbook.worksheets.add("参考对比明细");
  const issues = workbook.worksheets.add("差异明细");
  const style = workbook.worksheets.add("样式门明细");
  for (const sheet of [summary, stages, details, issues, style]) {
    sheet.showGridLines = false;
  }

  summary.getRange("A1:H1").merge();
  summary.getRange("A1").values = [["reference_comparison_report_v3_0"]];
  summary.getRange("A1").format = {
    fill: "#0F172A",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    verticalAlignment: "center",
  };
  summary.getRange("A2:H2").merge();
  summary.getRange("A2").values = [[
    "用途：汇总现有 staged/reference_compare/reference_style 证据。注意：这不是 fresh CAD 通过证明；SolidWorks 未响应时只能作为历史/现有证据索引。",
  ]];
  summary.getRange("A2").format = { fill: "#FFF7ED", font: { color: "#9A3412" }, wrapText: true };
  const detailEnd = Math.max(rows.length + 1, 2);
  const issueEnd = Math.max(issueRows.length + 1, 2);
  const styleEnd = Math.max(styleRows.length + 1, 2);
  summary.getRange("A4:B13").values = [
    ["指标", "值"],
    ["参考对比报告数", null],
    ["参考对比通过数", null],
    ["参考对比待复核数", null],
    ["参考对比失败数", null],
    ["样式门通过/豁免数", null],
    ["样式门待复核/失败数", null],
    ["差异记录数", null],
    ["阶段汇总数", null],
    ["报告生成时间", new Date()],
  ];
  summary.getRange("B5:B12").formulas = [
    [`=COUNTA('参考对比明细'!A2:A${detailEnd})`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"pass")+COUNTIF('参考对比明细'!E2:E${detailEnd},"pass_with_warning")+COUNTIF('参考对比明细'!E2:E${detailEnd},"no_reference")`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"need_review")`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"fail")`],
    [`=COUNTIF('样式门明细'!B2:B${styleEnd},"pass")+COUNTIF('样式门明细'!B2:B${styleEnd},"pass_with_warning")+COUNTIF('样式门明细'!B2:B${styleEnd},"no_reference")`],
    [`=COUNTIF('样式门明细'!B2:B${styleEnd},"need_review")+COUNTIF('样式门明细'!B2:B${styleEnd},"fail")`],
    [`=COUNTA('差异明细'!A2:A${issueEnd})`],
    [`=COUNTA('阶段汇总'!A2:A${Math.max(stageRows.length + 1, 2)})`],
  ];
  applyHeader(summary.getRange("A4:B4"));
  applyBody(summary.getRange("A5:B13"));
  summary.getRange("B13").setNumberFormat("yyyy-mm-dd hh:mm");
  summary.getRange("A15:H15").merge();
  summary.getRange("A15").values = [[
    `输出文件: ${outputPath}`,
  ]];
  summary.getRange("A15").format = { fill: "#E0F2FE", font: { color: "#075985" }, wrapText: true };
  summary.getRange("A1:H15").format.columnWidthPx = 150;
  summary.getRange("A1:H1").format.rowHeightPx = 34;
  summary.freezePanes.freezeRows(4);

  const stageHeader = ["阶段", "生成时间", "状态", "pass", "total", "processed", "deliverable", "need_review", "failed", "acceptance_pass", "summary.json"];
  writeRows(stages, 0, 0, [stageHeader]);
  writeRows(stages, 1, 0, stageRows.map((r) => [
    r.stage, r.generatedAt, r.status, r.pass, r.total, r.processed, r.deliverable, r.needReview, r.failed, r.acceptancePass, r.report,
  ]));
  applyHeader(stages.getRangeByIndexes(0, 0, 1, stageHeader.length));
  if (stageRows.length) applyBody(stages.getRangeByIndexes(1, 0, stageRows.length, stageHeader.length));
  stages.freezePanes.freezeRows(1);
  stages.getRange("A:K").format.columnWidthPx = 130;
  stages.getRange("K:K").format.columnWidthPx = 420;

  const detailHeader = [
    "阶段", "run_stamp", "case", "零件", "reference_status", "reference_pass", "style_status", "style_pass",
    "overall", "view", "dimension", "titlebar", "annotation", "layout", "ref_views", "gen_views",
    "ref_DisplayDim", "gen_DisplayDim", "差异数", "run_dir", "reference_compare.json", "style_source",
  ];
  writeRows(details, 0, 0, [detailHeader]);
  writeRows(details, 1, 0, rows.map((r) => [
    r.stage, r.runStamp, r.caseName, r.partName, r.status, r.pass, r.styleStatus, r.stylePass,
    r.overall, r.viewScore, r.dimensionScore, r.titlebarScore, r.annotationScore, r.layoutScore,
    r.refViews, r.genViews, r.refDims, r.genDims, r.differenceCount, r.runDir, r.reportPath, r.styleSource,
  ]));
  applyHeader(details.getRangeByIndexes(0, 0, 1, detailHeader.length));
  if (rows.length) applyBody(details.getRangeByIndexes(1, 0, rows.length, detailHeader.length));
  details.freezePanes.freezeRows(1);
  details.freezePanes.freezeColumns(4);
  details.getRange("A:V").format.columnWidthPx = 120;
  details.getRange("T:V").format.columnWidthPx = 360;
  details.getRange("I:N").setNumberFormat("0.000");
  details.getRange("O:S").setNumberFormat("#,##0");

  const issueHeader = ["阶段", "零件", "来源", "key", "severity", "reference", "generated", "fix_suggestion", "report"];
  writeRows(issues, 0, 0, [issueHeader]);
  writeRows(issues, 1, 0, issueRows.map((r) => [
    r.stage, r.partName, r.source, r.key, r.severity, r.reference, r.generated, r.fix, r.reportPath,
  ]));
  applyHeader(issues.getRangeByIndexes(0, 0, 1, issueHeader.length));
  if (issueRows.length) applyBody(issues.getRangeByIndexes(1, 0, issueRows.length, issueHeader.length));
  issues.freezePanes.freezeRows(1);
  issues.freezePanes.freezeColumns(2);
  issues.getRange("A:I").format.columnWidthPx = 150;
  issues.getRange("F:I").format.columnWidthPx = 300;

  const styleHeader = ["零件", "状态", "pass", "overall", "view", "dimension", "layout", "reasons", "source_report", "mtime"];
  writeRows(style, 0, 0, [styleHeader]);
  writeRows(style, 1, 0, styleRows.map((r) => [
    r.base, r.status, r.pass, r.overall, r.viewScore, r.dimScore, r.layoutScore, r.reasons, r.sourceReport, r.reportMtime,
  ]));
  applyHeader(style.getRangeByIndexes(0, 0, 1, styleHeader.length));
  if (styleRows.length) applyBody(style.getRangeByIndexes(1, 0, styleRows.length, styleHeader.length));
  style.freezePanes.freezeRows(1);
  style.getRange("A:J").format.columnWidthPx = 145;
  style.getRange("H:I").format.columnWidthPx = 360;
  style.getRange("D:G").setNumberFormat("0.000");

  summary.getRange("B5:B12").formulas = [
    [`=COUNTA('参考对比明细'!A2:A${detailEnd})`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"pass")+COUNTIF('参考对比明细'!E2:E${detailEnd},"pass_with_warning")+COUNTIF('参考对比明细'!E2:E${detailEnd},"no_reference")`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"need_review")`],
    [`=COUNTIF('参考对比明细'!E2:E${detailEnd},"fail")`],
    [`=COUNTIF('样式门明细'!B2:B${styleEnd},"pass")+COUNTIF('样式门明细'!B2:B${styleEnd},"pass_with_warning")+COUNTIF('样式门明细'!B2:B${styleEnd},"no_reference")`],
    [`=COUNTIF('样式门明细'!B2:B${styleEnd},"need_review")+COUNTIF('样式门明细'!B2:B${styleEnd},"fail")`],
    [`=COUNTA('差异明细'!A2:A${issueEnd})`],
    [`=COUNTA('阶段汇总'!A2:A${Math.max(stageRows.length + 1, 2)})`],
  ];

  const errorScan = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  console.log(errorScan.ndjson);

  const previewDir = path.join(drwOutput, "reference_comparison_report_preview");
  await fs.mkdir(previewDir, { recursive: true });
  for (const sheetName of ["总览", "阶段汇总", "参考对比明细", "差异明细", "样式门明细"]) {
    const blob = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
    const bytes = new Uint8Array(await blob.arrayBuffer());
    await fs.writeFile(path.join(previewDir, `${sheetName}.png`), bytes);
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
}

const outputPath = argValue("--out", defaultOut);
const { map: styleByBase, rows: styleRows } = await loadStyleGapByBase();
const stageRows = await loadStageSummaries();
const { rows, issueRows } = await loadComparisonRows(styleByBase);

await buildWorkbook({ rows, issueRows, stageRows, styleRows, outputPath });

console.log(JSON.stringify({
  pass: true,
  output: outputPath,
  reference_compare_count: rows.length,
  issue_count: issueRows.length,
  stage_summary_count: stageRows.length,
  style_gap_count: styleRows.length,
}, null, 2));
