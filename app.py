import io
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from ocr_engine import extract_text_lines_from_image
from rules_engine import evaluate_all_rules
from report_generator import generate_pdf_report
from database import get_connection
from crud import create_scan, create_scan_result, create_image, get_scan, get_scan_results_for_scan, get_images_for_scan, get_paginated_scans
from storage import upload_image, delete_image

app = FastAPI(
    title="PramanAI Compliance Engine",
    description="Automated Legal Metrology (Packaged Commodities) Rules, 2011 Verification Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for the latest generated scan report
latest_report_cache = {}

UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>PramanAI — LMPC Compliance Inspector</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        /* Smooth scrolling and native touch feel */
        html { -webkit-tap-highlight-color: transparent; }
        .custom-scrollbar::-webkit-scrollbar { height: 6px; width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col font-sans selection:bg-blue-600 selection:text-white">

    <!-- Top Navigation Bar -->
    <header class="bg-slate-800/90 backdrop-blur-md border-b border-slate-700 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-9 w-9 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/30">
                    <i class="fa-solid fa-scale-balanced text-white text-base"></i>
                </div>
                <div>
                    <h1 class="font-bold text-base sm:text-lg tracking-tight text-white leading-tight">PramanAI</h1>
                    <p class="text-[10px] sm:text-xs text-blue-400 font-medium tracking-wide leading-none">LMPC Act 2011 Engine</p>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    Live
                </span>
                <a href="/docs" target="_blank" class="p-2 text-slate-400 hover:text-white transition rounded-lg hover:bg-slate-700/50">
                    <i class="fa-solid fa-book-open text-sm"></i>
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-6 lg:p-8 space-y-6">
        
        <!-- Hero Header -->
        <div class="text-center sm:text-left space-y-1.5 pt-2">
            <h2 class="text-xl sm:text-2xl lg:text-3xl font-extrabold text-white tracking-tight">Package Label Audit</h2>
            <p class="text-xs sm:text-sm text-slate-400 max-w-2xl">
                Upload front/back packaging labels to detect statutory declarations under the Legal Metrology (Packaged Commodities) Rules, 2011.
            </p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6">
            
            <!-- Form Card (Left Column) -->
            <div class="lg:col-span-5 space-y-5">
                <div class="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-4 sm:p-6 shadow-xl space-y-5">
                    
                    <form id="auditForm" class="space-y-4" onsubmit="handleFormSubmit(event)">
                        
                        <!-- Upload Box -->
                        <div>
                            <label class="block text-xs sm:text-sm font-semibold text-slate-200 mb-2">Upload Label Image</label>
                            <div class="relative group">
                                <input type="file" id="imageInput" accept="image/*" required onchange="previewImage(this)"
                                    class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10">
                                <div id="dropZone" class="border-2 border-dashed border-slate-600 group-hover:border-blue-500 bg-slate-900/60 rounded-xl p-5 text-center transition flex flex-col items-center justify-center space-y-2.5">
                                    <div class="w-11 h-11 bg-slate-800 rounded-full flex items-center justify-center text-slate-400 group-hover:text-blue-400 group-hover:scale-105 transition">
                                        <i class="fa-solid fa-cloud-arrow-up text-lg"></i>
                                    </div>
                                    <div class="space-y-0.5">
                                        <p class="text-xs sm:text-sm font-medium text-slate-300" id="uploadText">Tap to capture or choose file</p>
                                        <p class="text-[10px] sm:text-xs text-slate-500">PNG, JPG up to 10MB</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Image Preview -->
                        <div id="previewContainer" class="hidden relative rounded-xl overflow-hidden border border-slate-700 bg-slate-950/80 max-h-52">
                            <img id="imagePreview" src="#" alt="Preview" class="w-full h-48 object-contain">
                            <button type="button" onclick="clearImage()" class="absolute top-2 right-2 bg-rose-600/90 text-white rounded-full p-1.5 shadow-md hover:bg-rose-500 transition">
                                <i class="fa-solid fa-xmark text-xs w-4 h-4 flex items-center justify-center"></i>
                            </button>
                        </div>

                        <!-- Physical Dimensions Card -->
                        <div class="bg-slate-900/50 border border-slate-700/60 rounded-xl p-3.5 space-y-3">
                            <p class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                                <i class="fa-solid fa-ruler-combined text-blue-400"></i> Dimensions & Font (Optional)
                            </p>
                            <div class="grid grid-cols-2 gap-2.5">
                                <div>
                                    <label class="block text-[11px] text-slate-400 mb-1">Height (cm)</label>
                                    <input type="number" step="0.1" id="pkg_height" value="15.0"
                                        class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
                                </div>
                                <div>
                                    <label class="block text-[11px] text-slate-400 mb-1">Width (cm)</label>
                                    <input type="number" step="0.1" id="pkg_width" value="10.0"
                                        class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
                                </div>
                                <div class="col-span-2">
                                    <label class="block text-[11px] text-slate-400 mb-1">Detected Font Height (mm)</label>
                                    <input type="number" step="0.1" id="font_height" value="2.5"
                                        class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
                                </div>
                            </div>
                        </div>

                        <!-- Submit Button -->
                        <button type="submit" id="submitBtn"
                            class="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl shadow-lg shadow-blue-500/25 transition active:scale-[0.99] flex items-center justify-center space-x-2 text-sm">
                            <i class="fa-solid fa-magnifying-glass"></i>
                            <span>Run Verification Audit</span>
                        </button>
                    </form>
                </div>
            </div>

            <!-- Results Column (Right Column) -->
            <div class="lg:col-span-7 space-y-5">
                
                <!-- Loading State -->
                <div id="loadingState" class="hidden bg-slate-800/60 border border-slate-700/60 rounded-2xl p-10 text-center space-y-3">
                    <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-slate-600 border-t-blue-500"></div>
                    <p class="text-sm font-medium text-slate-300">Scanning package declarations...</p>
                    <p class="text-xs text-slate-500">Extracting OCR tokens & cross-referencing LMPC Rules 2011</p>
                </div>

                <!-- Empty Initial State -->
                <div id="emptyState" class="bg-slate-800/40 border border-slate-700/50 border-dashed rounded-2xl p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-3">
                    <div class="w-14 h-14 bg-slate-800 rounded-2xl flex items-center justify-center text-slate-500">
                        <i class="fa-solid fa-clipboard-check text-2xl"></i>
                    </div>
                    <div class="space-y-1">
                        <p class="text-sm font-medium text-slate-300">No Inspection Results Yet</p>
                        <p class="text-xs text-slate-500 max-w-xs mx-auto">Upload a packaged product image on the left to generate the statutory compliance audit report.</p>
                    </div>
                </div>

                <!-- Live Results View -->
                <div id="resultsCard" class="hidden space-y-4">
                    
                    <!-- Score Banner -->
                    <div id="statusBanner" class="rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg border">
                        <div class="space-y-0.5">
                            <div class="flex items-center space-x-2">
                                <span id="statusIcon"></span>
                                <h3 id="statusTitle" class="text-base sm:text-lg font-bold"></h3>
                            </div>
                            <p id="statusSubtitle" class="text-xs opacity-90"></p>
                        </div>
                        <a href="/api/export-pdf" id="downloadPdfBtn"
                            class="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold bg-white text-slate-900 shadow hover:bg-slate-100 active:scale-95 transition">
                            <i class="fa-solid fa-file-arrow-down text-rose-600"></i>
                            <span>Download PDF Notice</span>
                        </a>
                    </div>

                    <!-- Misleading / Non-Standard Claims Advisory Card (Shown only if detected) -->
                    <div id="misleadingCard" class="hidden bg-amber-950/30 border border-amber-500/30 rounded-2xl p-4 shadow-lg space-y-3">
                        <div class="flex items-center justify-between">
                            <h4 class="text-xs sm:text-sm font-bold text-amber-300 flex items-center gap-2">
                                <i class="fa-solid fa-triangle-exclamation text-amber-400"></i> Advisory: Non-Standard / Misleading Declarations
                            </h4>
                            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase">Needs Review</span>
                        </div>
                        <p class="text-[11px] text-amber-200/80">The following non-standard or promotional declarations were identified and require human / legal verification:</p>
                        <div id="misleadingList" class="space-y-1.5 text-xs"></div>
                    </div>

                    <!-- Findings Table Card -->
                    <div class="bg-slate-800/80 border border-slate-700/80 rounded-2xl overflow-hidden shadow-xl">
                        <div class="p-3.5 sm:p-4 border-b border-slate-700/80 flex items-center justify-between">
                            <h4 class="text-xs sm:text-sm font-bold text-white flex items-center gap-2">
                                <i class="fa-solid fa-list-check text-blue-400"></i> Statutory Checkpoints
                            </h4>
                            <span id="scoreBadge" class="text-[11px] font-bold px-2.5 py-0.5 rounded-full"></span>
                        </div>

                        <!-- Horizontal Scroll Container for Mobile -->
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse min-w-[540px]">
                                <thead>
                                    <tr class="bg-slate-900/60 text-[11px] text-slate-400 font-semibold border-b border-slate-700/60 uppercase tracking-wider">
                                        <th class="py-2.5 px-3.5">Declaration Field</th>
                                        <th class="py-2.5 px-3">Statutory Rule</th>
                                        <th class="py-2.5 px-3 text-center">Status</th>
                                        <th class="py-2.5 px-3.5">Finding Details</th>
                                    </tr>
                                </thead>
                                <tbody id="resultsTableBody" class="divide-y divide-slate-700/40 text-xs">
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Extracted OCR Text Log Card -->
                    <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-4 space-y-2">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                                <i class="fa-solid fa-receipt text-slate-400"></i> Extracted OCR Tokens
                            </span>
                            <span id="tokenCount" class="text-[10px] text-slate-500 font-mono"></span>
                        </div>
                        <div id="ocrTokens" class="p-3 bg-slate-950/70 rounded-xl font-mono text-[11px] text-slate-400 max-h-36 overflow-y-auto space-y-1 custom-scrollbar">
                        </div>
                    </div>

                </div>

            </div>

        </div>

    </main>

    <!-- Footer -->
    <footer class="bg-slate-950 border-t border-slate-800 text-center py-4 px-4 text-slate-500 text-xs mt-auto">
        <p>PramanAI — Legal Metrology Act 2009 & Packaged Commodities Rules 2011 Automated Regulatory Engine</p>
    </footer>

    <script>
        function previewImage(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('imagePreview').src = e.target.result;
                    document.getElementById('previewContainer').classList.remove('hidden');
                    document.getElementById('uploadText').innerText = input.files[0].name;
                }
                reader.readAsDataURL(input.files[0]);
            }
        }

        function clearImage() {
            document.getElementById('imageInput').value = '';
            document.getElementById('imagePreview').src = '#';
            document.getElementById('previewContainer').classList.add('hidden');
            document.getElementById('uploadText').innerText = 'Tap to capture or choose file';
        }

        async function handleFormSubmit(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('imageInput');
            if (!fileInput.files || !fileInput.files[0]) {
                alert('Please upload an image first.');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('package_height_cm', document.getElementById('pkg_height').value || 15.0);
            formData.append('package_width_cm', document.getElementById('pkg_width').value || 10.0);
            formData.append('detected_font_height_mm', document.getElementById('font_height').value || 2.5);

            // Toggle States
            document.getElementById('emptyState').classList.add('hidden');
            document.getElementById('resultsCard').classList.add('hidden');
            document.getElementById('loadingState').classList.remove('hidden');
            document.getElementById('submitBtn').disabled = true;

            try {
                const res = await fetch('/api/scan-image', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Audit processing failed.');
                }

                const data = await res.json();
                renderResults(data);
            } catch (err) {
                alert('Error: ' + err.message);
                document.getElementById('emptyState').classList.remove('hidden');
            } finally {
                document.getElementById('loadingState').classList.add('hidden');
                document.getElementById('submitBtn').disabled = false;
            }
        }

        function renderResults(data) {
            const report = data.compliance_report;
            const status = report.status || (report.compliant ? 'PASS' : 'FAIL');

            // Status Banner
            const banner = document.getElementById('statusBanner');
            const icon = document.getElementById('statusIcon');
            const title = document.getElementById('statusTitle');
            const subtitle = document.getElementById('statusSubtitle');
            const scoreBadge = document.getElementById('scoreBadge');

            if (status === 'PASS') {
                banner.className = 'rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg border bg-emerald-950/40 border-emerald-500/30 text-emerald-300';
                icon.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400 text-lg sm:text-xl"></i>';
                title.innerText = 'Fully Compliant';
                subtitle.innerText = 'All statutory declarations detected and validated.';
                scoreBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
            } else if (status === 'NEEDS REVIEW') {
                banner.className = 'rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg border bg-amber-950/40 border-amber-500/30 text-amber-300';
                icon.innerHTML = '<i class="fa-solid fa-eye text-amber-400 text-lg sm:text-xl"></i>';
                title.innerText = 'Manual Review Required';
                subtitle.innerText = 'Low-confidence OCR reads or non-standard declarations need manual verification.';
                scoreBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30';
            } else {
                banner.className = 'rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg border bg-rose-950/40 border-rose-500/30 text-rose-300';
                icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-rose-400 text-lg sm:text-xl"></i>';
                title.innerText = 'Non-Compliance Detected';
                subtitle.innerText = 'One or more mandatory statutory declarations are missing or invalid.';
                scoreBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30';
            }
            scoreBadge.innerText = report.score;

            // Findings Table
            const tbody = document.getElementById('resultsTableBody');
            tbody.innerHTML = '';

            report.results.forEach(item => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';

                const itemStatus = item.status || (item.pass ? 'PASS' : 'FAIL');

                const statusPill = itemStatus === 'PASS' 
                    ? '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">PASS</span>'
                    : itemStatus === 'NEEDS REVIEW'
                    ? '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">NEEDS REVIEW</span>'
                    : '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">FAIL</span>';

                tr.innerHTML = `
                    <td class="py-2.5 px-3.5 font-medium text-slate-200">${item.field}</td>
                    <td class="py-2.5 px-3 text-slate-400 font-mono text-[11px]">${item.rule}</td>
                    <td class="py-2.5 px-3 text-center">${statusPill}</td>
                    <td class="py-2.5 px-3.5 text-slate-300 text-[11px]">${item.reason}</td>
                `;
                tbody.appendChild(tr);
            });

            // Misleading Declarations Advisory Card
            const misleadingCard = document.getElementById('misleadingCard');
            const misleadingList = document.getElementById('misleadingList');
            const misleadingInfo = report.misleading_declarations;

            if (misleadingInfo && misleadingInfo.detected && misleadingInfo.findings && misleadingInfo.findings.length > 0) {
                misleadingCard.classList.remove('hidden');
                misleadingList.innerHTML = '';
                misleadingInfo.findings.forEach(f => {
                    const div = document.createElement('div');
                    div.className = 'p-2.5 rounded-xl bg-amber-900/20 border border-amber-500/20 text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-[11px]';
                    div.innerHTML = `
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-white bg-amber-500/30 px-2 py-0.5 rounded text-[10px]">'${f.claim}'</span>
                            <span class="text-amber-200/90">${f.reason}</span>
                        </div>
                        <span class="text-[10px] font-semibold text-amber-400 shrink-0 uppercase tracking-wide bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">${f.category}</span>
                    `;
                    misleadingList.appendChild(div);
                });
            } else {
                misleadingCard.classList.add('hidden');
            }

            // Raw OCR Token Display
            const tokensBox = document.getElementById('ocrTokens');
            tokensBox.innerHTML = '';
            document.getElementById('tokenCount').innerText = `${data.detected_raw_lines.length} lines detected`;

            data.detected_raw_lines.forEach(line => {
                const div = document.createElement('div');
                div.className = 'text-slate-300 py-0.5 border-b border-slate-900/40 last:border-0';
                div.textContent = `> ${line}`;
                tokensBox.appendChild(div);
            });

            document.getElementById('resultsCard').classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def root_redirect():
    """Root URL — redirects to UI."""
    return HTMLResponse(content=UI_HTML)

@app.get("/ui", response_class=HTMLResponse)
def get_user_interface():
    """Serves the responsive, mobile-first inspector UI."""
    return HTMLResponse(content=UI_HTML)

@app.post("/api/scan-image")
async def scan_package_image(
    file: UploadFile = File(...),
    package_height_cm: float = Form(15.0),
    package_width_cm: float = Form(10.0),
    detected_font_height_mm: float = Form(2.5)
):
    """
    Ingests label image bytes, extracts OCR tokens, runs LMPC validation,
    and caches the latest report for PDF export.
    """
    global latest_report_cache
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid image (PNG/JPG).")

    image_bytes = await file.read()
    raw_lines = extract_text_lines_from_image(image_bytes)

    compliance_results = evaluate_all_rules(
        raw_lines=raw_lines,
        package_height_cm=package_height_cm,
        package_width_cm=package_width_cm,
        detected_font_height_mm=detected_font_height_mm
    )

    # Database Persistence & Storage Upload (Step 7 Integration)
    conn = None
    uploaded_storage_path = None
    try:
        conn = get_connection()
        scan_id = create_scan(
            conn,
            product_id=None,
            user_id=None,
            image_url=None,  # scans.image_url remains None
            overall_verdict=compliance_results.get("status"),
            font_height_detected=detected_font_height_mm,
            org=None,
            ocr_raw_text=raw_lines
        )

        # Determine safe file extension
        ext = "png"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        elif file.content_type:
            if "jpeg" in file.content_type or "jpg" in file.content_type:
                ext = "jpg"
            elif "png" in file.content_type:
                ext = "png"

        storage_path = f"scan-{scan_id}/original.{ext}"
        content_type = file.content_type or f"image/{ext}"

        # Upload image to Supabase Storage
        upload_image(image_bytes=image_bytes, storage_path=storage_path, content_type=content_type)
        uploaded_storage_path = storage_path

        # Create images record in PostgreSQL referencing Storage path
        create_image(
            conn,
            scan_id=scan_id,
            image_url=storage_path,
            image_type=None
        )

        # Create scan_results records
        for result in compliance_results.get("results", []):
            create_scan_result(
                conn,
                scan_id=scan_id,
                rule_code=result["rule"],
                status=result["status"],
                finding_detail=result.get("reason")
            )

        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        
        # Rollback storage upload if DB transaction failed after storage upload
        if uploaded_storage_path:
            try:
                delete_image(uploaded_storage_path)
            except Exception as cleanup_err:
                print(f"Cleanup Failure: Could not remove {uploaded_storage_path}: {cleanup_err}")

        raise HTTPException(status_code=500, detail=f"Database & storage transaction failed: {str(e)}")
    finally:
        if conn:
            conn.close()

    response_payload = {
        "status": "success",
        "scan_id": scan_id,
        "detected_raw_lines": raw_lines,
        "compliance_report": compliance_results
    }

    # Store for PDF generator
    latest_report_cache = response_payload

    return response_payload


@app.post("/api/scan-images")
async def scan_package_images(
    files: list[UploadFile] = File(...),
    package_height_cm: float = Form(15.0),
    package_width_cm: float = Form(10.0),
    detected_font_height_mm: float = Form(2.5)
):
    """
    Multi-image packaging inspection endpoint (Step 8).
    Accepts 1 to 5 images, extracts combined OCR tokens,
    executes LMPC rules evaluation once, uploads files to Supabase Storage,
    and persists records in PostgreSQL scans, images, and scan_results tables.
    """
    global latest_report_cache

    MAX_IMAGES = 5

    if not files or len(files) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"Number of images must be between 1 and {MAX_IMAGES}.")

    # Validate content types & read file binaries
    image_payloads = []
    combined_raw_lines = []

    for idx, file_obj in enumerate(files):
        if not file_obj.content_type or not file_obj.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="All uploaded files must be images.")

        file_bytes = await file_obj.read()
        lines = extract_text_lines_from_image(file_bytes)
        combined_raw_lines.extend(lines)

        image_payloads.append({
            "file_bytes": file_bytes,
            "filename": file_obj.filename,
            "content_type": file_obj.content_type,
            "image_type": None
        })

    # Evaluate rules engine ONCE across combined OCR lines
    compliance_results = evaluate_all_rules(
        raw_lines=combined_raw_lines,
        package_height_cm=package_height_cm,
        package_width_cm=package_width_cm,
        detected_font_height_mm=detected_font_height_mm
    )

    conn = None
    uploaded_storage_paths = []
    persisted_images_meta = []

    try:
        conn = get_connection()
        
        # 1. Create single scan row
        scan_id = create_scan(
            conn,
            product_id=None,
            user_id=None,
            image_url=None,  # scans.image_url remains NULL
            overall_verdict=compliance_results.get("status"),
            font_height_detected=detected_font_height_mm,
            org=None,
            ocr_raw_text=combined_raw_lines
        )

        # 2. Upload each image to Supabase Storage & insert into images table
        for idx, item in enumerate(image_payloads):
            img_type = item["image_type"]
            ext = "png"
            if item["filename"] and "." in item["filename"]:
                ext = item["filename"].rsplit(".", 1)[-1].lower()
            elif item["content_type"]:
                if "jpeg" in item["content_type"] or "jpg" in item["content_type"]:
                    ext = "jpg"

            storage_path = f"scan-{scan_id}/img_{idx + 1}.{ext}"
            content_type = item["content_type"] or f"image/{ext}"

            upload_image(
                image_bytes=item["file_bytes"],
                storage_path=storage_path,
                content_type=content_type
            )
            uploaded_storage_paths.append(storage_path)

            img_id = create_image(
                conn,
                scan_id=scan_id,
                image_url=storage_path,
                image_type=img_type
            )

            persisted_images_meta.append({
                "image_id": img_id,
                "image_type": img_type,
                "image_url": storage_path
            })

        # 3. Create scan_results records once for the scan
        for result in compliance_results.get("results", []):
            create_scan_result(
                conn,
                scan_id=scan_id,
                rule_code=result["rule"],
                status=result["status"],
                finding_detail=result.get("reason")
            )

        conn.commit()

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass

        # Cleanup all uploaded storage objects if DB transaction fails
        for path in uploaded_storage_paths:
            try:
                delete_image(path)
            except Exception as cleanup_err:
                print(f"Cleanup Error: Failed to remove {path}: {cleanup_err}")

        raise HTTPException(status_code=500, detail=f"Multi-image scan transaction failed: {str(e)}")
    finally:
        if conn:
            conn.close()

    response_payload = {
        "status": "success",
        "scan_id": scan_id,
        "detected_raw_lines": combined_raw_lines,
        "compliance_report": compliance_results,
        "images": persisted_images_meta
    }

    latest_report_cache = response_payload
    return response_payload

def parse_filter_date(date_str: str, is_end_date: bool = False):
    d_str = date_str.strip()
    from datetime import datetime
    try:
        if "T" in d_str or " " in d_str:
            d_str_iso = d_str.replace(" ", "T")
            return datetime.fromisoformat(d_str_iso)
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        if is_end_date:
            return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except Exception:
        target = "end_date" if is_end_date else "start_date"
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {target} format '{date_str}'. Expected ISO 8601 string or YYYY-MM-DD format."
        )


@app.get("/api/scans")
def get_scans(
    page: int = Query(1),
    page_size: int = Query(10),
    status: str | None = Query(None),
    failed_rule: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    product_name: str | None = Query(None),
    brand: str | None = Query(None),
    inspector: str | None = Query(None)
):
    """
    Retrieves paginated scan history records from PostgreSQL ordered newest-first
    (timestamp DESC, scan_id DESC) with optional search & filtering parameters.
    Independent of in-memory latest_report_cache.
    """
    MAX_PAGE_SIZE = 100
    ALLOWED_STATUSES = {"PASS", "FAIL", "NEEDS REVIEW"}

    if page < 1:
        raise HTTPException(status_code=400, detail="page must be greater than or equal to 1.")

    if page_size < 1:
        raise HTTPException(status_code=400, detail="page_size must be greater than or equal to 1.")

    if page_size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"page_size cannot exceed maximum allowed limit of {MAX_PAGE_SIZE}.")

    norm_status = None
    if status is not None and status.strip():
        norm_status = status.strip().upper()
        if norm_status not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter '{status}'. Allowed values: 'PASS', 'FAIL', 'NEEDS REVIEW'."
            )

    parsed_start_date = None
    if start_date is not None and start_date.strip():
        parsed_start_date = parse_filter_date(start_date, is_end_date=False)

    parsed_end_date = None
    if end_date is not None and end_date.strip():
        parsed_end_date = parse_filter_date(end_date, is_end_date=True)

    norm_failed_rule = None
    if failed_rule is not None and failed_rule.strip():
        norm_failed_rule = failed_rule.strip()

    conn = None
    try:
        conn = get_connection()
        res_data = get_paginated_scans(
            conn,
            page=page,
            page_size=page_size,
            status=norm_status,
            failed_rule=norm_failed_rule,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            product_name=product_name,
            brand=brand,
            inspector=inspector
        )

        formatted_items = []
        for item in res_data.get("items", []):
            ocr_data = item.get("ocr_raw_text")
            raw_lines = []
            if ocr_data is not None:
                if isinstance(ocr_data, list):
                    raw_lines = ocr_data
                elif isinstance(ocr_data, str):
                    import json
                    try:
                        raw_lines = json.loads(ocr_data)
                    except Exception:
                        raw_lines = [ocr_data]

            font_height = item.get("font_height_detected")
            if font_height is not None:
                font_height = float(font_height)

            formatted_items.append({
                "scan_id": item["scan_id"],
                "timestamp": item["timestamp"],
                "overall_verdict": item["overall_verdict"],
                "font_height_detected": font_height,
                "ocr": {
                    "raw_lines": raw_lines
                },
                "product_id": item.get("product_id"),
                "user_id": item.get("user_id"),
                "org": item.get("org")
            })

        return {
            "items": formatted_items,
            "page": res_data["page"],
            "page_size": res_data["page_size"],
            "total": res_data["total"],
            "total_pages": res_data["total_pages"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scan history: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/api/scans/{scan_id}")
def get_scan_by_id(scan_id: int):
    """
    Retrieves a persisted scan record, its associated scan_results,
    and image references by scan_id from PostgreSQL.
    Independent of in-memory latest_report_cache.
    """
    conn = None
    try:
        conn = get_connection()
        scan_record = get_scan(conn, scan_id)
        if not scan_record:
            raise HTTPException(status_code=404, detail="Scan not found")

        results_records = get_scan_results_for_scan(conn, scan_id)
        images_records = get_images_for_scan(conn, scan_id)

        # Parse ocr_raw_text cleanly
        ocr_data = scan_record.get("ocr_raw_text")
        raw_lines = []
        if ocr_data is not None:
            if isinstance(ocr_data, list):
                raw_lines = ocr_data
            elif isinstance(ocr_data, str):
                import json
                try:
                    raw_lines = json.loads(ocr_data)
                except Exception:
                    raw_lines = [ocr_data]

        font_height = scan_record.get("font_height_detected")
        if font_height is not None:
            font_height = float(font_height)

        response_payload = {
            "scan_id": scan_record["scan_id"],
            "timestamp": scan_record["timestamp"],
            "overall_verdict": scan_record["overall_verdict"],
            "font_height_detected": font_height,
            "ocr": {
                "raw_lines": raw_lines
            },
            "results": [
                {
                    "result_id": r["result_id"],
                    "rule_code": r["rule_code"],
                    "status": r["status"],
                    "finding_detail": r["finding_detail"],
                    "created_at": r["created_at"]
                }
                for r in results_records
            ],
            "images": [
                {
                    "image_id": img["image_id"],
                    "image_url": img["image_url"],
                    "image_type": img["image_type"],
                    "created_at": img["created_at"]
                }
                for img in images_records
            ],
            "product_id": scan_record.get("product_id"),
            "user_id": scan_record.get("user_id"),
            "org": scan_record.get("org")
        }

        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scan record: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/api/export-pdf")
def export_official_notice_pdf():
    """Compiles and downloads the Official Digital Inspection Notice PDF."""
    global latest_report_cache
    if not latest_report_cache:
        raise HTTPException(status_code=400, detail="No scan data found. Please perform an inspection scan first.")

    output_pdf_path = "PramanAI_Inspection_Notice.pdf"
    generate_pdf_report(latest_report_cache, output_path=output_pdf_path)

    return FileResponse(
        path=output_pdf_path,
        media_type="application/pdf",
        filename="PramanAI_Inspection_Notice.pdf"
    )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    for schema_name, schema_val in schemas.items():
        if "scan_package_images" in schema_name and "properties" in schema_val:
            files_prop = schema_val["properties"].get("files", {})
            if files_prop.get("type") == "array" and "items" in files_prop:
                files_prop["items"]["format"] = "binary"
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi