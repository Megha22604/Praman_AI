import io
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from ocr_engine import extract_text_lines_from_image
from rules_engine import evaluate_all_rules
from report_generator import generate_pdf_report

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
    <title>Pramand_AI — LMPC Compliance Inspector</title>
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
                    <h1 class="font-bold text-base sm:text-lg tracking-tight text-white leading-tight">Pramand_AI</h1>
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
        <p>Pramand_AI — Legal Metrology Act 2009 & Packaged Commodities Rules 2011 Automated Regulatory Engine</p>
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
            const isCompliant = report.compliant;

            // Status Banner
            const banner = document.getElementById('statusBanner');
            const icon = document.getElementById('statusIcon');
            const title = document.getElementById('statusTitle');
            const subtitle = document.getElementById('statusSubtitle');
            const scoreBadge = document.getElementById('scoreBadge');

            if (isCompliant) {
                banner.className = 'rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg border bg-emerald-950/40 border-emerald-500/30 text-emerald-300';
                icon.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400 text-lg sm:text-xl"></i>';
                title.innerText = 'Fully Compliant';
                subtitle.innerText = 'All mandatory statutory declarations detected and validated.';
                scoreBadge.className = 'text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
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

                const statusPill = item.pass 
                    ? '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">PASS</span>'
                    : '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">FAIL</span>';

                tr.innerHTML = `
                    <td class="py-2.5 px-3.5 font-medium text-slate-200">${item.field}</td>
                    <td class="py-2.5 px-3 text-slate-400 font-mono text-[11px]">${item.rule}</td>
                    <td class="py-2.5 px-3 text-center">${statusPill}</td>
                    <td class="py-2.5 px-3.5 text-slate-300 text-[11px]">${item.reason}</td>
                `;
                tbody.appendChild(tr);
            });

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

    response_payload = {
        "status": "success",
        "detected_raw_lines": raw_lines,
        "compliance_report": compliance_results
    }

    # Store for PDF generator
    latest_report_cache = response_payload

    return response_payload

@app.get("/api/export-pdf")
def export_official_notice_pdf():
    """Compiles and downloads the Official Digital Inspection Notice PDF."""
    global latest_report_cache
    if not latest_report_cache:
        raise HTTPException(status_code=400, detail="No scan data found. Please perform an inspection scan first.")

    output_pdf_path = "Pramand_AI_Inspection_Notice.pdf"
    generate_pdf_report(latest_report_cache, output_path=output_pdf_path)

    return FileResponse(
        path=output_pdf_path,
        media_type="application/pdf",
        filename="Pramand_AI_Inspection_Notice.pdf"
    )