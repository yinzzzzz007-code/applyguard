import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(process.cwd());
const SKILL_DIR = "C:/Users/84032/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const TMP_DIR = path.join(workspaceDir, ".build", "presentation");
const FINAL_PPTX = path.join(workspaceDir, "presentation", "applyguard-proposal-foundation-final.pptx");
const RUNTIME_PYTHON = "C:/Users/84032/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";

const {
  resolvePresentationFont,
  makeNativeBulletParagraphs,
  finalizePresentation,
} = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const fontFamily = resolvePresentationFont();
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const C = {
  navy: "#172033",
  ink: "#25344A",
  muted: "#65758B",
  pale: "#F4F6F8",
  bluePale: "#E9EFF7",
  blue: "#486A94",
  crimson: "#9F1D2E",
  crimsonPale: "#FCEAEC",
  gold: "#A36B00",
  goldPale: "#FFF4DA",
  green: "#3F6B45",
  greenPale: "#EEF5EC",
  line: "#D9E0E8",
  white: "#FFFFFF",
};

function addShape(slide, geometry, position, fill, line = { fill: "none", width: 0 }) {
  return slide.shapes.add({ geometry, position, fill, line });
}

function addText(slide, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: options.fontSize ?? 24,
    bold: options.bold ?? false,
    color: options.color ?? C.ink,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: "none",
  };
  return shape;
}

function addBullets(slide, items, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = makeNativeBulletParagraphs(items, {
    marginLeftPoints: options.marginLeftPoints ?? 18,
    hangingPoints: options.hangingPoints ?? 9,
    spaceAfterPoints: options.spaceAfterPoints ?? 8,
  });
  shape.text.style = {
    typeface: fontFamily,
    fontSize: options.fontSize ?? 23,
    color: options.color ?? C.ink,
    autoFit: "none",
  };
  return shape;
}

function baseSlide(title, number) {
  const slide = presentation.slides.add();
  slide.background.fill = C.white;
  addShape(slide, "rect", { left: 0, top: 0, width: 14, height: 720 }, C.crimson);
  addText(slide, title, { left: 62, top: 42, width: 1120, height: 64 }, {
    fontSize: 38,
    bold: true,
    color: C.navy,
  });
  addShape(slide, "line", { left: 62, top: 116, width: 1150, height: 1 }, "none", {
    fill: C.line,
    width: 1,
  });
  addText(slide, String(number).padStart(2, "0"), { left: 1170, top: 665, width: 52, height: 24 }, {
    fontSize: 15,
    color: C.muted,
    alignment: "right",
  });
  return slide;
}

function note(slide, extra = "") {
  slide.speakerNotes.textFrame.setText(
    `Sources: Project_Kickoff.pdf, pages 5-7; team plan at https://my.feishu.cn/wiki/DAZgwqkIYixhoQk18E7cFlwhngb; docs/proposal-scope.md.${extra ? ` ${extra}` : ""}`,
  );
}

function labelBox(slide, text, position, options = {}) {
  const shape = addShape(
    slide,
    options.geometry ?? "roundRect",
    position,
    options.fill ?? C.pale,
    { fill: options.line ?? C.ink, width: options.lineWidth ?? 1.4 },
  );
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: options.fontSize ?? 18,
    bold: options.bold ?? true,
    color: options.color ?? C.ink,
    alignment: "center",
    verticalAlignment: "middle",
    autoFit: "none",
  };
  return shape;
}

// 1. Title
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addShape(slide, "rect", { left: 74, top: 112, width: 90, height: 10 }, C.crimson);
  addText(slide, "ApplyGuard", { left: 74, top: 166, width: 900, height: 100 }, {
    fontSize: 66,
    bold: true,
    color: C.white,
  });
  addText(slide, "Evidence-grounded job applications with human control", { left: 78, top: 286, width: 920, height: 70 }, {
    fontSize: 28,
    color: "#DCE5EF",
  });
  addText(slide, "Software Engineering Project Proposal", { left: 78, top: 560, width: 720, height: 34 }, {
    fontSize: 20,
    color: "#AAB9CA",
  });
  addText(slide, "Proposal foundation  |  10 October 2026", { left: 78, top: 606, width: 720, height: 30 }, {
    fontSize: 17,
    color: "#AAB9CA",
  });
  note(slide);
}

// 2. Problem
{
  const slide = baseSlide("Problem", 2);
  addText(slide, "Applicants repeatedly turn scattered experience into job-specific claims.", { left: 68, top: 154, width: 1070, height: 86 }, {
    fontSize: 34,
    bold: true,
    color: C.navy,
  });
  addShape(slide, "rect", { left: 70, top: 276, width: 8, height: 240 }, C.crimson);
  addText(slide, "Current tools can improve wording while losing the connection to evidence, hiding uncertainty, or creating unsupported statements.", { left: 108, top: 278, width: 750, height: 150 }, {
    fontSize: 27,
    color: C.ink,
  });
  addText(slide, "The missing control", { left: 884, top: 292, width: 300, height: 38 }, { fontSize: 20, bold: true, color: C.crimson });
  addText(slide, "Trace every claim\nExplain every selection\nStop before submission", { left: 884, top: 346, width: 300, height: 150 }, {
    fontSize: 24,
    color: C.ink,
  });
  note(slide);
}

// 3. Target user
{
  const slide = baseSlide("Target User", 3);
  const rows = [
    ["Primary user", "University students and recent graduates applying for internships or entry-level software roles"],
    ["Available evidence", "Course projects, internships, volunteer work, repositories, reports, and certificates"],
    ["Decision pressure", "Select relevant experience, avoid exaggeration, and confirm risky ATS fields before submission"],
    ["Study input", "B will run 10-20 lightweight surveys and 4-6 semi-structured interviews before the proposal"],
  ];
  rows.forEach(([label, value], i) => {
    const y = 158 + i * 112;
    addText(slide, label, { left: 72, top: y, width: 240, height: 34 }, { fontSize: 21, bold: true, color: i === 3 ? C.crimson : C.navy });
    addText(slide, value, { left: 332, top: y - 2, width: 820, height: 70 }, { fontSize: 24, color: C.ink });
    if (i < rows.length - 1) addShape(slide, "line", { left: 72, top: y + 78, width: 1080, height: 1 }, "none", { fill: C.line, width: 1 });
  });
  note(slide, "User-study sample sizes come from the team plan and are planned, not completed results.");
}

// 4. Related work
{
  const slide = baseSlide("Related Work and Project Gap", 4);
  const x = [72, 438, 804];
  const headings = ["General writing assistants", "Resume builders", "ApplyGuard gap"];
  const bodies = [
    "Useful for rewriting and drafting. They may not retain structured evidence or expose unsupported fragments.",
    "Useful for formatting and templates. They often treat source experience as free text and stop before ATS risk checks.",
    "A single inspectable path connects evidence, job requirements, resume claims, ATS fields, visible risks, and user confirmation.",
  ];
  headings.forEach((heading, i) => {
    addText(slide, heading, { left: x[i], top: 176, width: 322, height: 62 }, { fontSize: 24, bold: true, color: i === 2 ? C.crimson : C.navy });
    addShape(slide, "line", { left: x[i], top: 246, width: 300, height: 1 }, "none", { fill: i === 2 ? C.crimson : C.line, width: i === 2 ? 3 : 1 });
    addText(slide, bodies[i], { left: x[i], top: 276, width: 312, height: 236 }, { fontSize: 23, color: C.ink });
  });
  note(slide, "This slide describes product categories and the project gap without claiming measured market coverage.");
}

// 5. Scope
{
  const slide = baseSlide("Proposal Scope", 5);
  addText(slide, "P0 foundation", { left: 74, top: 154, width: 480, height: 42 }, { fontSize: 27, bold: true, color: C.navy });
  addBullets(slide, [
    "One runnable mock workflow",
    "Frozen JSON contracts and error format",
    "Fictional Career Vault data",
    "Evidence IDs on every selected claim",
    "Human confirmation before any submission",
  ], { left: 74, top: 214, width: 520, height: 300 }, { fontSize: 22, spaceAfterPoints: 11 });
  addText(slide, "Outside the proposal", { left: 696, top: 154, width: 480, height: 42 }, { fontSize: 27, bold: true, color: C.crimson });
  addBullets(slide, [
    "Automatic application submission",
    "Support for every ATS platform",
    "Production identity verification",
    "Claims without stored evidence",
    "Measured accuracy before evaluation",
  ], { left: 696, top: 214, width: 490, height: 300 }, { fontSize: 22, spaceAfterPoints: 11 });
  addShape(slide, "rect", { left: 74, top: 560, width: 1110, height: 72 }, C.bluePale, { fill: C.blue, width: 1 });
  addText(slide, "Core scope: three user stories and one complete main workflow", { left: 104, top: 578, width: 1040, height: 38 }, {
    fontSize: 24, bold: true, color: C.navy, alignment: "center",
  });
  note(slide);
}

// 6. Workflow
{
  const slide = baseSlide("End-to-End Workflow", 6);
  const topXs = [52, 296, 540, 784, 1028];
  const topLabels = ["1\nCareer Vault", "2\nJD Parser", "3\nEvidence Matcher", "4\nResume Selector", "5\nClaim Validator"];
  const top = topLabels.map((label, i) => labelBox(slide, label, { left: topXs[i], top: 192, width: 200, height: 86 }, {
    fill: i === 4 ? C.crimsonPale : C.pale,
    line: i === 4 ? C.crimson : C.ink,
    color: i === 4 ? C.crimson : C.ink,
  }));
  const bottomXs = [904, 660, 416, 172];
  const bottomLabels = ["6\nATS Form Mapper", "7\nRisk Check", "8\nHuman Confirmation", "9\nAudit Record"];
  const bottom = bottomLabels.map((label, i) => labelBox(slide, label, { left: bottomXs[i], top: 420, width: 200, height: 86 }, {
    fill: i === 1 ? C.crimsonPale : i === 2 ? C.goldPale : i === 3 ? C.greenPale : C.pale,
    line: i === 1 ? C.crimson : i === 2 ? C.gold : i === 3 ? C.green : C.ink,
    color: i === 1 ? C.crimson : i === 2 ? C.gold : i === 3 ? C.green : C.ink,
  }));
  for (let i = 0; i < top.length - 1; i++) {
    slide.shapes.connect(top[i], top[i + 1], { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow", width: "med", length: "med" } });
  }
  slide.shapes.connect(top[4], bottom[0], { kind: "elbow", fromSide: "bottom", toSide: "top", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow", width: "med", length: "med" } });
  for (let i = 0; i < bottom.length - 1; i++) {
    slide.shapes.connect(bottom[i], bottom[i + 1], { kind: "straight", fromSide: "left", toSide: "right", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow", width: "med", length: "med" } });
  }
  addText(slide, "The proposal demo ends with an auditable draft. It does not submit an application.", { left: 170, top: 570, width: 930, height: 44 }, {
    fontSize: 23, bold: true, color: C.crimson, alignment: "center",
  });
  note(slide);
}

// 7. Architecture
{
  const slide = baseSlide("System Architecture", 7);
  const user = labelBox(slide, "Applicant", { left: 52, top: 300, width: 170, height: 72 }, { geometry: "ellipse", fill: C.white });
  const ui = labelBox(slide, "Web UI and\nATS Simulator", { left: 278, top: 290, width: 190, height: 92 }, { fill: C.bluePale, line: C.blue });
  const orchestrator = labelBox(slide, "Workflow\nOrchestrator", { left: 520, top: 290, width: 190, height: 92 }, { fill: "#DDE8F4", line: C.blue });
  const data = labelBox(slide, "Career Vault\nand contracts", { left: 762, top: 176, width: 190, height: 84 }, { fill: C.pale });
  const intelligence = labelBox(slide, "Parser, matcher,\nselector, validator", { left: 762, top: 300, width: 190, height: 84 }, { fill: C.crimsonPale, line: C.crimson, color: C.crimson });
  const control = labelBox(slide, "Risk check and\nhuman confirmation", { left: 762, top: 424, width: 190, height: 84 }, { fill: C.goldPale, line: C.gold, color: C.gold });
  const audit = labelBox(slide, "Audit Record", { left: 1020, top: 300, width: 190, height: 84 }, { fill: C.greenPale, line: C.green, color: C.green });
  slide.shapes.connect(user, ui, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow" } });
  slide.shapes.connect(ui, orchestrator, { kind: "straight", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow" } });
  [data, intelligence, control].forEach((target) => slide.shapes.connect(orchestrator, target, { kind: "elbow", fromSide: "right", toSide: "left", line: { style: "solid", fill: C.muted, width: 2 }, tail: { type: "arrow" } }));
  [data, intelligence, control].forEach((source) => slide.shapes.connect(source, audit, { kind: "elbow", fromSide: "right", toSide: "left", line: { style: "dashed", fill: C.muted, width: 1.6 }, tail: { type: "arrow", width: "sm", length: "sm" } }));
  addText(slide, "Module contracts let B, C, and D replace internals without redesigning the full system.", { left: 200, top: 586, width: 880, height: 42 }, { fontSize: 22, color: C.navy, alignment: "center" });
  note(slide);
}

// 8. Technical core
{
  const slide = baseSlide("Technical Core and AI Boundary", 8);
  const columns = [
    ["Deterministic code", ["Schema validation", "Scores and constraints", "State transitions", "Confirmation gate"]],
    ["AI-assisted modules", ["JD requirement extraction", "Claim drafting", "Explanation generation", "Provider fallback"]],
    ["Enforced evidence", ["Evidence IDs", "Unsupported-fragment detection", "Visible risk reasons", "Audit trace"]],
  ];
  const xs = [70, 440, 810];
  columns.forEach(([heading, items], i) => {
    addText(slide, heading, { left: xs[i], top: 170, width: 320, height: 44 }, { fontSize: 25, bold: true, color: i === 1 ? C.crimson : C.navy });
    addShape(slide, "line", { left: xs[i], top: 228, width: 310, height: 1 }, "none", { fill: i === 1 ? C.crimson : C.line, width: i === 1 ? 3 : 1 });
    addText(slide, items.join("\n\n"), { left: xs[i], top: 258, width: 320, height: 290 }, { fontSize: 23, color: C.ink });
  });
  addText(slide, "AI can propose content. Contracts, checks, and the applicant decide what proceeds.", { left: 140, top: 584, width: 1000, height: 42 }, { fontSize: 25, bold: true, color: C.crimson, alignment: "center" });
  note(slide);
}

// 9. Risks and evaluation
{
  const slide = baseSlide("Risks and Evaluation Plan", 9);
  const rows = [
    ["Unsupported claim", "Block the fragment and show its missing evidence", "Unsupported Claim Block Rate"],
    ["Wrong JD extraction", "Retain source text and compare parsed fields", "JD Parsing Accuracy"],
    ["Malformed model output", "Validate JSON and use a deterministic fallback", "Failure Test Suite"],
    ["Confusing risk message", "Run task-based usability testing after the proposal", "Completion, time, errors, SUS"],
  ];
  addText(slide, "Risk", { left: 72, top: 154, width: 260, height: 32 }, { fontSize: 19, bold: true, color: C.muted });
  addText(slide, "Mitigation", { left: 348, top: 154, width: 500, height: 32 }, { fontSize: 19, bold: true, color: C.muted });
  addText(slide, "Planned evidence", { left: 866, top: 154, width: 320, height: 32 }, { fontSize: 19, bold: true, color: C.muted });
  rows.forEach(([risk, mitigation, evidence], i) => {
    const y = 204 + i * 106;
    addShape(slide, "line", { left: 72, top: y - 14, width: 1115, height: 1 }, "none", { fill: C.line, width: 1 });
    addText(slide, risk, { left: 72, top: y, width: 250, height: 70 }, { fontSize: 22, bold: true, color: i === 0 ? C.crimson : C.navy });
    addText(slide, mitigation, { left: 348, top: y, width: 480, height: 72 }, { fontSize: 21, color: C.ink });
    addText(slide, evidence, { left: 866, top: y, width: 310, height: 72 }, { fontSize: 21, color: C.ink });
  });
  note(slide);
}

// 10. Team plan
{
  const slide = baseSlide("Team Plan", 10);
  const rows = [
    ["A", "1-2 Oct", "Scope, architecture, contracts, repository foundation, handoff"],
    ["B", "3-4 Oct", "Career Vault, evidence matching, formative user study"],
    ["C", "5-6 Oct", "JD parser, claim validation, risk engine, failure tests"],
    ["D", "7-8 Oct", "Frontend integration, demo flow, presentation assembly"],
  ];
  rows.forEach(([owner, date, work], i) => {
    const y = 166 + i * 112;
    addText(slide, owner, { left: 74, top: y, width: 70, height: 56 }, { fontSize: 34, bold: true, color: i === 0 ? C.crimson : C.navy, alignment: "center" });
    addText(slide, date, { left: 176, top: y + 4, width: 160, height: 44 }, { fontSize: 21, bold: true, color: C.muted });
    addText(slide, work, { left: 354, top: y, width: 800, height: 62 }, { fontSize: 23, color: C.ink });
    if (i < rows.length - 1) addShape(slide, "line", { left: 72, top: y + 82, width: 1080, height: 1 }, "none", { fill: C.line, width: 1 });
  });
  addShape(slide, "rect", { left: 72, top: 620, width: 1080, height: 5 }, C.crimson);
  note(slide);
}

// 11. Demo
{
  const slide = baseSlide("Proposal Demo", 11);
  const steps = [
    ["01", "Load fictional Career Vault evidence"],
    ["02", "Paste one software-engineering job description"],
    ["03", "Inspect evidence matches and selected resume claim"],
    ["04", "Show the risk result and human-confirmation gate"],
  ];
  steps.forEach(([number, text], i) => {
    const y = 154 + i * 104;
    addText(slide, number, { left: 76, top: y, width: 70, height: 46 }, { fontSize: 25, bold: true, color: C.crimson });
    addText(slide, text, { left: 170, top: y, width: 880, height: 54 }, { fontSize: 27, color: C.ink });
    addShape(slide, "line", { left: 170, top: y + 65, width: 850, height: 1 }, "none", { fill: C.line, width: 1 });
  });
  addShape(slide, "roundRect", { left: 800, top: 552, width: 380, height: 78 }, C.goldPale, { fill: C.gold, width: 1.5 });
  addText(slide, "Stop before submission", { left: 830, top: 573, width: 320, height: 38 }, { fontSize: 25, bold: true, color: C.gold, alignment: "center" });
  note(slide);
}

for (let i = 0; i < presentation.slides.items.length; i++) {
  const slide = presentation.slides.items[i];
  const preview = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(TMP_DIR, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "applyguard-proposal-foundation.candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 11,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
};
const result = await finalizePresentation({
  ...requirements,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: { basis: "design", families: [fontFamily] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "applyguard-proposal-foundation-final.validation.json"),
});

console.log(JSON.stringify({ final: FINAL_PPTX, fontFamily, validation: result }, null, 2));
