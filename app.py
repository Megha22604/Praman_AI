from fastapi.responses import FileResponse, HTMLResponse
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from parser import parse_raw_ocr_lines
from rules_engine import validate_label
from report_generator import generate_pdf_report
from ocr_engine import extract_text_lines_from_image
from fastapi.responses import FileResponse
from report_generator import generate_pdf_report
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from parser import parse_raw_ocr_lines
from rules_engine import validate_label

app = FastAPI(
    title="LMPC Legal Metrology Compliance Engine",
    version="1.0.0"
)

class PackageMetadataInput(BaseModel):
    shape: str = "rectangular"
    height_cm: Optional[float] = 0.0
    width_cm: Optional[float] = 0.0
    circumference_cm: Optional[float] = 0.0
    total_surface_area_cm2: Optional[float] = 0.0
    is_blown: bool = False

class ScanRequest(BaseModel):
    raw_ocr_lines: List[str]
    font_height_mm: Optional[float] = None
    metadata: Optional[PackageMetadataInput] = None

@app.get("/")
def root():
    return {"status": "online", "system": "LMPC Rules Compliance API"}

@app.post("/api/audit")
def audit_label(request: ScanRequest):
    # Step 1: Parse raw OCR lines into structured fields
    parsed_fields = parse_raw_ocr_lines(request.raw_ocr_lines)

    # Step 2: Attach spatial measurements if provided
    if request.font_height_mm is not None:
        parsed_fields["font_height_mm"] = request.font_height_mm
    
    if request.metadata:
        parsed_fields["metadata"] = request.metadata.model_dump()

    # Step 3: Run deterministic legal verification
    report = validate_label(parsed_fields)

    return {
        "parsed_fields": parsed_fields,
        "compliance_report": report
    }
@app.post("/api/audit/pdf")
def audit_and_generate_pdf(request: ScanRequest):
    # Process compliance check
    parsed_fields = parse_raw_ocr_lines(request.raw_ocr_lines)
    if request.font_height_mm is not None:
        parsed_fields["font_height_mm"] = request.font_height_mm
    if request.metadata:
        parsed_fields["metadata"] = request.metadata.model_dump()

    report = validate_label(parsed_fields)
    
    # Generate PDF
    pdf_filename = "inspection_report.pdf"
    generate_pdf_report({"compliance_report": report}, output_path=pdf_filename)
    
    return FileResponse(
        path=pdf_filename,
        media_type="application/pdf",
        filename=pdf_filename
    )
@app.post("/api/scan-image")
async def scan_package_image(
    file: UploadFile = File(...),
    shape: str = Form("rectangular"),
    height_cm: float = Form(0.0),
    width_cm: float = Form(0.0),
    font_height_mm: Optional[float] = Form(None)
):
    # 1. Read uploaded image bytes and run OCR
    image_bytes = await file.read()
    raw_lines = extract_text_lines_from_image(image_bytes)

    # 2. Parse detected text into legal entities
    parsed_fields = parse_raw_ocr_lines(raw_lines)
    
    # 3. Attach spatial measurements
    parsed_fields["font_height_mm"] = font_height_mm
    parsed_fields["metadata"] = {
        "shape": shape,
        "height_cm": height_cm,
        "width_cm": width_cm,
        "circumference_cm": 0.0,
        "total_surface_area_cm2": 0.0,
        "is_blown": False
    }

    # 4. Run rules validation
    report = validate_label(parsed_fields)

    return {
        "ocr_detected_lines": raw_lines,
        "parsed_fields": parsed_fields,
        "compliance_report": report
    }
@app.get("/ui", response_class=HTMLResponse)
def serve_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pramand_AI — Food Metrology & Packaging Intelligence</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-base: #f7f9f6;
                --surface-card: #ffffff;
                --surface-subtle: #f0f4ee;
                --surface-hover: #eaf1e8;
                
                --primary: #1e4a38;
                --primary-accent: #2e6f54;
                --primary-light: #e8f3ee;
                --primary-border: #c8dfd4;
                
                --olive: #557153;
                --honey: #b45309;
                --honey-bg: #fef3c7;
                
                --border: #e1e8df;
                --border-focus: #2e6f54;
                
                --text-main: #14241d;
                --text-muted: #5e7368;
                --text-subtle: #8a9e94;
                
                --pass-bg: #ecf8f1;
                --pass-text: #196c44;
                --pass-border: #b7e4cb;
                
                --fail-bg: #fdf2f2;
                --fail-text: #a82323;
                --fail-border: #f8b4b4;

                --shadow-sm: 0 1px 3px rgba(20, 36, 29, 0.04), 0 1px 2px rgba(20, 36, 29, 0.02);
                --shadow-md: 0 4px 16px -2px rgba(20, 36, 29, 0.06), 0 2px 6px -1px rgba(20, 36, 29, 0.03);
                --shadow-lg: 0 12px 32px -4px rgba(20, 36, 29, 0.08), 0 4px 12px -2px rgba(20, 36, 29, 0.03);
            }

            * { box-sizing: border-box; margin: 0; padding: 0; }
            html, body {
                width: 100%;
                min-height: 100vh;
                background-color: var(--bg-base);
                font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
                color: var(--text-main);
                font-size: 13.5px;
                line-height: 1.5;
                -webkit-font-smoothing: antialiased;
            }

            /* Top Bar */
            .navbar {
                background: rgba(255, 255, 255, 0.85);
                backdrop-filter: blur(16px);
                border-bottom: 1px solid var(--border);
                position: sticky;
                top: 0;
                z-index: 50;
                padding: 14px 28px;
            }
            .navbar-inner {
                max-width: 1320px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .brand-group {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .brand-icon {
                width: 34px;
                height: 34px;
                background: linear-gradient(135deg, #1e4a38 0%, #2e6f54 100%);
                color: #ffffff;
                border-radius: 10px;
                display: grid;
                place-items: center;
                font-size: 16px;
                box-shadow: 0 4px 10px rgba(30, 74, 56, 0.2);
            }
            .brand-title {
                font-size: 16px;
                font-weight: 800;
                letter-spacing: -0.4px;
                color: var(--primary);
            }
            .brand-badge {
                font-size: 11px;
                font-weight: 600;
                background: var(--primary-light);
                color: var(--primary);
                padding: 3px 9px;
                border-radius: 20px;
                border: 1px solid var(--primary-border);
            }
            .meta-pill {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 12px;
                color: var(--text-muted);
                background: var(--surface-subtle);
                padding: 6px 12px;
                border-radius: 20px;
                border: 1px solid var(--border);
            }
            .live-dot {
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #10b981;
                box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
            }

            /* Container */
            .container {
                max-width: 1320px;
                margin: 28px auto;
                padding: 0 24px;
            }

            /* Tabs */
            .tab-nav {
                display: inline-flex;
                background: var(--surface-subtle);
                padding: 4px;
                border-radius: 12px;
                border: 1px solid var(--border);
                margin-bottom: 24px;
                gap: 4px;
            }
            .tab-btn {
                padding: 8px 18px;
                border: none;
                background: transparent;
                font-family: inherit;
                font-size: 13px;
                font-weight: 600;
                color: var(--text-muted);
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .tab-btn.active {
                background: #ffffff;
                color: var(--primary);
                box-shadow: var(--shadow-sm);
            }

            /* Main Layout Grid */
            .main-grid {
                display: grid;
                grid-template-columns: 360px minmax(0, 1fr);
                gap: 24px;
                align-items: start;
            }
            @media (max-width: 980px) {
                .main-grid { grid-template-columns: 1fr; }
            }

            /* Card Styling */
            .card {
                background: var(--surface-card);
                border: 1px solid var(--border);
                border-radius: 16px;
                box-shadow: var(--shadow-md);
                overflow: hidden;
            }
            .card-header {
                padding: 16px 20px;
                border-bottom: 1px solid var(--border);
                background: linear-gradient(180deg, #ffffff 0%, var(--surface-subtle) 100%);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .card-title {
                font-size: 13.5px;
                font-weight: 700;
                color: var(--primary);
                letter-spacing: -0.2px;
            }
            .card-body {
                padding: 20px;
            }

            /* Dropzone Preview */
            .dropzone {
                border: 2px dashed var(--primary-border);
                background: #fbfdfa;
                border-radius: 12px;
                height: 150px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                margin-bottom: 16px;
                transition: all 0.2s ease;
            }
            .dropzone:hover {
                background: var(--primary-light);
                border-color: var(--primary-accent);
            }
            .dropzone img {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }

            /* Sophisticated Inputs */
            .field-wrap { margin-bottom: 14px; }
            .label {
                display: block;
                font-size: 11.5px;
                font-weight: 600;
                color: var(--text-muted);
                margin-bottom: 6px;
            }
            input[type="text"], input[type="number"], select, textarea {
                width: 100%;
                padding: 10px 14px;
                border-radius: 10px;
                border: 1px solid var(--border);
                background: #ffffff;
                font-family: inherit;
                font-size: 13px;
                color: var(--text-main);
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            }
            input:focus, select:focus, textarea:focus {
                outline: none;
                border-color: var(--primary-accent);
                box-shadow: 0 0 0 3px rgba(46, 111, 84, 0.12);
            }
            .grid-2 {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }

            /* File Upload Button */
            .file-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                width: 100%;
                padding: 10px;
                background: var(--surface-subtle);
                border: 1px solid var(--border);
                border-radius: 10px;
                font-weight: 600;
                font-size: 12.5px;
                color: var(--primary);
                cursor: pointer;
                transition: all 0.2s;
                margin-bottom: 14px;
            }
            .file-btn:hover {
                background: var(--surface-hover);
                border-color: var(--primary-border);
            }
            input[type="file"] { display: none; }

            /* Primary Buttons */
            .btn-action {
                width: 100%;
                padding: 12px 18px;
                border: none;
                border-radius: 10px;
                font-family: inherit;
                font-size: 13.5px;
                font-weight: 700;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                transition: all 0.2s ease;
            }
            .btn-audit {
                background: linear-gradient(135deg, #1e4a38 0%, #2e6f54 100%);
                color: #ffffff;
                box-shadow: 0 4px 12px rgba(30, 74, 56, 0.2);
            }
            .btn-audit:hover {
                box-shadow: 0 6px 18px rgba(30, 74, 56, 0.28);
                transform: translateY(-1px);
            }
            .btn-audit:active { transform: translateY(0); }

            .btn-pdf {
                background: #ffffff;
                color: var(--primary);
                border: 1.5px solid var(--primary-border);
                font-size: 12.5px;
                padding: 7px 14px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s;
            }
            .btn-pdf:hover {
                background: var(--primary-light);
                border-color: var(--primary-accent);
            }

            /* Findings Overview Callout */
            .overview-card {
                background: #ffffff;
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 18px 24px;
                margin-bottom: 20px;
                box-shadow: var(--shadow-sm);
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 16px;
            }
            .overview-card.pass {
                border-left: 5px solid var(--pass-text);
                background: linear-gradient(90deg, var(--pass-bg) 0%, #ffffff 100%);
            }
            .overview-card.fail {
                border-left: 5px solid var(--fail-text);
                background: linear-gradient(90deg, var(--fail-bg) 0%, #ffffff 100%);
            }
            .status-title {
                font-size: 15px;
                font-weight: 700;
                margin-bottom: 3px;
            }
            .status-desc {
                font-size: 12px;
                color: var(--text-muted);
            }
            .score-chip {
                font-family: 'JetBrains Mono', monospace;
                font-size: 18px;
                font-weight: 700;
                padding: 6px 16px;
                border-radius: 30px;
                background: #ffffff;
                box-shadow: var(--shadow-sm);
                border: 1px solid var(--border);
            }

            /* Clean Findings Table */
            .table-wrap {
                width: 100%;
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                font-size: 13px;
                text-align: left;
            }
            th {
                padding: 12px 16px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                color: var(--text-muted);
                background: var(--surface-subtle);
                border-bottom: 1px solid var(--border);
            }
            th:first-child { border-top-left-radius: 10px; }
            th:last-child { border-top-right-radius: 10px; }

            td {
                padding: 13px 16px;
                border-bottom: 1px solid var(--border);
                vertical-align: middle;
                color: var(--text-main);
            }
            tr:last-child td { border-bottom: none; }
            tr:hover td { background: #fafdfa; }

            .pill {
                display: inline-flex;
                align-items: center;
                gap: 5px;
                padding: 3px 9px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            .pill-pass {
                background: var(--pass-bg);
                color: var(--pass-text);
                border: 1px solid var(--pass-border);
            }
            .pill-fail {
                background: var(--fail-bg);
                color: var(--fail-text);
                border: 1px solid var(--fail-border);
            }

            .rule-badge {
                font-family: 'JetBrains Mono', monospace;
                font-size: 11.5px;
                color: var(--primary);
                font-weight: 600;
                background: var(--surface-subtle);
                padding: 2px 7px;
                border-radius: 4px;
            }

            /* JSON Preview Panels */
            pre {
                font-family: 'JetBrains Mono', monospace;
                font-size: 11.5px;
                background: #fbfdfa;
                border: 1px solid var(--border);
                color: var(--text-main);
                padding: 14px;
                border-radius: 10px;
                max-height: 180px;
                overflow-x: auto;
                line-height: 1.5;
            }

            .empty-view {
                padding: 60px 20px;
                text-align: center;
                color: var(--text-muted);
                font-size: 13.5px;
            }
        </style>
    </head>
    <body>

        <!-- Navigation Bar -->
        <header class="navbar">
            <div class="navbar-inner">
                <div class="brand-group">
                    <div class="brand-icon">🌱</div>
                    <span class="brand-title">Pramand_AI</span>
                    <span class="brand-badge">PCR 2011 Metrology</span>
                </div>
                <div class="meta-pill">
                    <div class="live-dot"></div>
                    <span>Rules Engine v1.2 Active</span>
                </div>
            </div>
        </header>

        <div class="container">
            
            <!-- Tab Controls -->
            <div class="tab-nav">
                <button class="tab-btn active" onclick="switchTab('image')">Optical Image Scan</button>
                <button class="tab-btn" onclick="switchTab('json')">Direct Data Simulator</button>
            </div>

            <div class="main-grid">
                
                <!-- Left Input Controls -->
                <div class="card">
                    
                    <!-- Optical Mode -->
                    <div id="imagePanel">
                        <div class="card-header">
                            <span class="card-title">Packaging Evidence</span>
                        </div>
                        <div class="card-body">
                            <div class="dropzone">
                                <span id="dropzoneText" style="font-size: 12px; color: var(--text-subtle);">No image selected</span>
                                <img id="imagePreview" style="display: none;" />
                            </div>

                            <label for="imageInput" class="file-btn">
                                <span>📁 Choose Label Photo</span>
                            </label>
                            <input type="file" id="imageInput" accept="image/*" onchange="previewLabelImage(event)">

                            <div class="field-wrap">
                                <label class="label">Packaging Geometry</label>
                                <select id="shapeInput">
                                    <option value="rectangular">Rectangular (Carton / Box / Pouch)</option>
                                    <option value="cylindrical">Cylindrical (Bottle / Jar / Can)</option>
                                </select>
                            </div>

                            <div class="grid-2 field-wrap">
                                <div>
                                    <label class="label">Height (cm)</label>
                                    <input type="number" id="heightInput" value="15.0" step="0.1">
                                </div>
                                <div>
                                    <label class="label">Width (cm)</label>
                                    <input type="number" id="widthInput" value="10.0" step="0.1">
                                </div>
                            </div>

                            <div class="field-wrap" style="margin-bottom: 20px;">
                                <label class="label">Measured Font Height (mm)</label>
                                <input type="number" id="fontInput" value="2.5" step="0.1">
                            </div>

                            <button class="btn-action btn-audit" onclick="runImageAudit()">
                                🌿 Run Regulatory Verification
                            </button>
                        </div>
                    </div>

                    <!-- Direct JSON Mode -->
                    <div id="jsonPanel" style="display: none;">
                        <div class="card-header">
                            <span class="card-title">OCR Line Stream</span>
                        </div>
                        <div class="card-body">
                            <div class="field-wrap">
                                <label class="label">OCR Detected Lines (JSON Array)</label>
                                <textarea id="rawLinesInput" rows="10" style="font-family: 'JetBrains Mono', monospace; font-size: 11px;">[
  "ORGANIC GREEN TEA",
  "Net Qty: 200 g",
  "MRP Rs. 149.00 (Incl. of all taxes)",
  "USP: Rs. 0.745 / g",
  "Mfg Date: 03/2026",
  "Manufactured by: Pramand Organics Pvt Ltd, Pune 411001",
  "Consumer Care: support@pramand.com, Toll Free 1800-111-2222",
  "Country of Origin: India"
]</textarea>
                            </div>

                            <div class="field-wrap" style="margin-bottom: 20px;">
                                <label class="label">Font Height (mm)</label>
                                <input type="number" id="jsonFontInput" value="2.8" step="0.1">
                            </div>

                            <button class="btn-action btn-audit" onclick="runJsonAudit()">
                                🌿 Audit Data Array
                            </button>
                        </div>
                    </div>

                </div>

                <!-- Right Findings Section -->
                <div>
                    <div id="emptyView" class="card empty-view">
                        Select an image or payload on the left to review the compliance evaluation and export reports.
                    </div>

                    <div id="resultsDashboard" style="display: none;">
                        
                        <!-- Overview Status -->
                        <div id="summaryCard" class="overview-card">
                            <div>
                                <div id="statusHeading" class="status-title"></div>
                                <div class="status-desc">Assessment under Legal Metrology (Packaged Commodities) Rules, 2011</div>
                            </div>
                            <div id="scoreDisplay" class="score-chip"></div>
                        </div>

                        <!-- Findings Table Card -->
                        <div class="card" style="margin-bottom: 20px;">
                            <div class="card-header">
                                <span class="card-title">Statutory Rule Findings</span>
                                <button class="btn-pdf" onclick="downloadNoticePdf()">📄 Export Official Notice (PDF)</button>
                            </div>

                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr>
                                            <th style="width: 26%;">Mandatory Field</th>
                                            <th style="width: 18%;">Rule Cited</th>
                                            <th style="width: 14%;">Status</th>
                                            <th style="width: 42%;">Inspector Findings</th>
                                        </tr>
                                    </thead>
                                    <tbody id="findingsTableBody"></tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Extraction Details -->
                        <div class="grid-2">
                            <div class="card">
                                <div class="card-header">
                                    <span class="card-title">Parsed Legal Entities</span>
                                </div>
                                <div class="card-body" style="padding: 12px;">
                                    <pre id="parsedEntitiesBlock"></pre>
                                </div>
                            </div>
                            <div class="card">
                                <div class="card-header">
                                    <span class="card-title">Raw Text Stream</span>
                                </div>
                                <div class="card-body" style="padding: 12px;">
                                    <pre id="rawOcrBlock"></pre>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>

            </div>
        </div>

        <script>
            let activeAuditPayload = null;

            function switchTab(mode) {
                const buttons = document.querySelectorAll('.tab-btn');
                buttons.forEach(b => b.classList.remove('active'));
                
                if (mode === 'image') {
                    buttons[0].classList.add('active');
                    document.getElementById('imagePanel').style.display = 'block';
                    document.getElementById('jsonPanel').style.display = 'none';
                } else {
                    buttons[1].classList.add('active');
                    document.getElementById('imagePanel').style.display = 'none';
                    document.getElementById('jsonPanel').style.display = 'block';
                }
            }

            function previewLabelImage(e) {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(evt) {
                        const img = document.getElementById('imagePreview');
                        img.src = evt.target.result;
                        img.style.display = 'block';
                        document.getElementById('dropzoneText').style.display = 'none';
                    };
                    reader.readAsDataURL(file);
                }
            }

            function renderComplianceDashboard(data, fontHeight, metadata, rawLines) {
                document.getElementById('emptyView').style.display = 'none';
                document.getElementById('resultsDashboard').style.display = 'block';

                const report = data.compliance_report;
                const summaryCard = document.getElementById('summaryCard');
                const statusHeading = document.getElementById('statusHeading');
                const scoreDisplay = document.getElementById('scoreDisplay');

                if (report.compliant) {
                    summaryCard.className = 'overview-card pass';
                    statusHeading.innerHTML = '✅ Fully Compliant';
                    statusHeading.style.color = 'var(--pass-text)';
                    scoreDisplay.style.color = 'var(--pass-text)';
                } else {
                    summaryCard.className = 'overview-card fail';
                    statusHeading.innerHTML = '⚠️ Non-Compliance Detected';
                    statusHeading.style.color = 'var(--fail-text)';
                    scoreDisplay.style.color = 'var(--fail-text)';
                }

                scoreDisplay.innerText = `${report.score} (${report.percentage}%)`;

                const tbody = document.getElementById('findingsTableBody');
                tbody.innerHTML = '';
                report.results.forEach(r => {
                    const pillClass = r.pass ? 'pill-pass' : 'pill-fail';
                    const pillText = r.pass ? 'PASS' : 'FAIL';
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${r.field}</strong></td>
                            <td><span class="rule-badge">${r.rule}</span></td>
                            <td><span class="pill ${pillClass}">${pillText}</span></td>
                            <td>${r.reason}</td>
                        </tr>
                    `;
                });

                document.getElementById('parsedEntitiesBlock').innerText = JSON.stringify(data.parsed_fields, null, 2);
                document.getElementById('rawOcrBlock').innerText = JSON.stringify(data.ocr_detected_lines || rawLines, null, 2);

                activeAuditPayload = {
                    raw_ocr_lines: data.ocr_detected_lines || rawLines,
                    font_height_mm: fontHeight,
                    metadata: metadata
                };
            }

            async function runImageAudit() {
                const fileInput = document.getElementById('imageInput');
                if (!fileInput.files[0]) {
                    alert("Please select a packaging label photo first.");
                    return;
                }

                const fontHeight = parseFloat(document.getElementById('fontInput').value);
                const metadata = {
                    shape: document.getElementById('shapeInput').value,
                    height_cm: parseFloat(document.getElementById('heightInput').value),
                    width_cm: parseFloat(document.getElementById('widthInput').value),
                    circumference_cm: 0.0,
                    total_surface_area_cm2: 0.0,
                    is_blown: false
                };

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('shape', metadata.shape);
                formData.append('height_cm', metadata.height_cm);
                formData.append('width_cm', metadata.width_cm);
                formData.append('font_height_mm', fontHeight);

                try {
                    const res = await fetch('/api/scan-image', { method: 'POST', body: formData });
                    const data = await res.json();
                    renderComplianceDashboard(data, fontHeight, metadata, data.ocr_detected_lines);
                } catch (err) {
                    alert("Audit execution failed: " + err.message);
                }
            }

            async function runJsonAudit() {
                try {
                    const rawLines = JSON.parse(document.getElementById('rawLinesInput').value);
                    const fontHeight = parseFloat(document.getElementById('jsonFontInput').value);
                    const metadata = { shape: "rectangular", height_cm: 15.0, width_cm: 10.0, is_blown: false };

                    const res = await fetch('/api/audit', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            raw_ocr_lines: rawLines,
                            font_height_mm: fontHeight,
                            metadata: metadata
                        })
                    });
                    const data = await res.json();
                    renderComplianceDashboard(data, fontHeight, metadata, rawLines);
                } catch (err) {
                    alert("Invalid JSON format or server error: " + err.message);
                }
            }

            async function downloadNoticePdf() {
                if (!activeAuditPayload) return;

                const res = await fetch('/api/audit/pdf', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(activeAuditPayload)
                });

                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "Pramand_AI_Inspection_Notice.pdf";
                document.body.appendChild(a);
                a.click();
                a.remove();
            }
        </script>
    </body>
    </html>
    """