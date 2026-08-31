# Antigravity IDE Prompt — PramanAI: Backlog Task 2 (Automatic Physical Dimension Calibration)

Paste this whole document into Antigravity as the task brief. Work through
the phases **in order**, each with a working, testable checkpoint before
moving to the next. Assume the project is currently in its original state —
no calibration code exists yet, package height/width are still typed in
manually.

---

## Project Context

Repo: PramanAI (SIH26034) — FastAPI backend. Key existing files:

- `app.py` — API + inline HTML/JS UI. `POST /api/scan-image` currently takes
  `file`, `package_height_cm` (Form, default 15.0), `package_width_cm` (Form,
  default 10.0), `detected_font_height_mm` (Form, default 2.5). The UI has a
  "Dimensions & Font (Optional)" card with three manual number inputs for
  these.
- `rules_engine.py` — `evaluate_all_rules(raw_lines, package_height_cm=15.0,
  package_width_cm=10.0, detected_font_height_mm=2.5)` builds an
  `extracted_data["metadata"]` dict from the manual inputs, feeds it to
  `validate_label()`, which calls `calculate_pdp_area()` and
  `validate_pdp_font_height()` for the Rule 7(2) statutory check.
- `ocr_engine.py` — OCR only. **Do not touch this file** — it's owned by a
  different teammate's task (OCR quality / font-height auto-detection is
  separate work, out of scope here).
- `test_rules.py`, `run_pipeline.py` — call `validate_label()` directly with
  hand-built `metadata` dicts. **These must keep working unmodified** — don't
  change `validate_label()`'s signature or behavior when `metadata` is
  present, only add a new path for when it's absent.

**Decision already made — build to this spec, don't re-litigate it:**
- Reference-object method: **ArUco marker** (not credit-card detection).
- Manual height/width fields are **fully replaced**, not supplemented — no
  fallback manual entry. If calibration can't measure dimensions, the app
  says so explicitly rather than falling back to a guess.

**Deliverable:** Package height/width are measured automatically from an
ArUco marker placed in the photo — the manual "Height (cm)" / "Width (cm)"
fields are removed from the UI and the API entirely.

---

## Phase 0 — Confirm the baseline (read-only, ~10 min)

**0.1** — Read `app.py`'s `/api/scan-image` endpoint and the UI's dimension
input section. Read `rules_engine.py`'s `evaluate_all_rules()`,
`validate_label()`, and `calculate_pdp_area()`. Confirm your understanding of
exactly where `package_height_cm`/`package_width_cm` flow from form input to
the Rule 7(2) check, before changing anything.

✅ Checkpoint: you can describe the current data flow in one sentence before
touching code.

---

## Phase 1 — New module: `calibration.py` skeleton

**1.1** — Create a new file `calibration.py`. Add:
- Constant `ARUCO_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)`
  (chosen for robustness at small print sizes / low-res phone photos).
- Constant `ARUCO_MARKER_ID = 0`.
- Constant `DEFAULT_MARKER_SIZE_MM = 40.0` — the real-world side length of
  the printed marker. This must match whatever Phase 5's generator produces.
- A private helper `_load_cv_image(image_bytes: bytes) -> np.ndarray` that
  opens the bytes with PIL, converts to RGB, converts to a BGR numpy array
  for OpenCV.

✅ Checkpoint: file imports cleanly (`import calibration` doesn't error),
constants are defined.

---

## Phase 2 — Marker detection

**2.1** — Write `detect_aruco_marker(image_bytes: bytes, marker_size_mm:
float = DEFAULT_MARKER_SIZE_MM) -> dict | None`:
- Convert to grayscale, run `cv2.aruco.ArucoDetector(ARUCO_DICTIONARY,
  cv2.aruco.DetectorParameters()).detectMarkers(gray)`.
- Return `None` if no marker found.
- If found, compute the marker's average side length in pixels (mean of the
  4 edge lengths from its corner points), then `pixels_per_mm = avg_side_px
  / marker_size_mm`.
- Return a dict: `{"marker_id": int, "pixels_per_mm": float,
  "marker_bbox_px": (x0, y0, x1, y1), "image_shape": (h, w)}`.
- **Watch for this OpenCV gotcha:** `ids` from `detectMarkers()` has an
  inconsistent shape across OpenCV versions ((N,1) vs (N,)) — flatten it
  defensively (`np.asarray(ids).flatten()[0]`) rather than indexing `ids[0][0]`
  directly, or you'll hit an `IndexError` on some installs.

**2.2** — Test standalone before moving on: generate a synthetic test image
with `cv2.aruco.generateImageMarker()` at a known pixel size (e.g. 400px =
40mm, so 10px/mm), run `detect_aruco_marker()` against it, and confirm the
returned `pixels_per_mm` is close to 10.0.

✅ Checkpoint: detection works on a synthetic marker with a known, verifiable
pixels-per-mm result — confirmed via a quick script, not just "looks right."

---

## Phase 3 — Package bounding box detection

**3.1** — Write `detect_package_bbox_px(image_bytes: bytes, exclude_bbox_px:
tuple | None = None) -> tuple | None`:
- Grayscale → Gaussian blur → Canny edge detection → dilate to close gaps →
  `cv2.findContours` with `RETR_EXTERNAL`.
- For each contour, take its bounding rect. Reject boxes that are too small
  (<1% of image area — noise) or too large (>95% — likely the whole frame,
  not the package). Reject any box that overlaps the marker's bbox (passed
  in via `exclude_bbox_px`) so the marker itself isn't mistaken for the
  package.
- Return the largest remaining candidate as `(x, y, w, h)` in pixels, or
  `None` if nothing plausible is found.

**3.2** — Test standalone with a synthetic scene: white canvas, marker placed
in one corner, a solid dark rectangle elsewhere at a *known* pixel size.
Confirm the detected bbox matches the known rectangle, not the marker.

✅ Checkpoint: package bbox detection correctly ignores the marker region and
finds the right object in a controlled synthetic test.

---

## Phase 4 — Full calibration orchestration

**4.1** — Write `calibrate_package_dimensions(image_bytes: bytes,
marker_size_mm: float = DEFAULT_MARKER_SIZE_MM) -> dict`:
- Call `detect_aruco_marker()`. If `None`, return
  `{"success": False, "message": "No ArUco calibration marker detected. Print
  the <N>mm marker..., place it flat next to the product (fully visible, not
  tilted), and rescan."}` — **no fabricated fallback dimensions**, this is a
  hard requirement, not a nice-to-have.
- Otherwise call `detect_package_bbox_px()`, excluding the marker's bbox. If
  `None`, return `{"success": False, "message": "Calibration marker detected,
  but the package outline could not be isolated. Retake the photo with the
  product and marker both flat, well-lit, and against a plain background."}`.
- Otherwise convert the package bbox's pixel width/height to real-world
  centimetres using the marker's `pixels_per_mm`, and return
  `{"success": True, "height_cm": ..., "width_cm": ..., "pixels_per_mm": ...,
  "marker_id": ...}` (round to 2 decimals for cm, 3 for the ratio).

**4.2** — End-to-end test with the same synthetic scene from Phase 3, at a
*known* real-world size (e.g. marker=40mm defines scale, rectangle drawn at
exactly what should compute to 150mm × 100mm). Confirm the returned
`height_cm`/`width_cm` are close to the known values (some error from edge
padding is expected and fine — flag if it's off by more than ~5%).

**4.3** — Test the explicit failure path too: a synthetic image with *no*
marker at all should return `success: False` with the no-marker message, not
raise an exception or return zeros.

✅ Checkpoint: both the success and failure paths of
`calibrate_package_dimensions()` are verified against synthetic test images
with known ground truth.

---

## Phase 5 — Printable marker generator + endpoint

**5.1** — In `calibration.py`, write `generate_marker_png_bytes(marker_size_px:
int = 600, marker_size_mm: float = DEFAULT_MARKER_SIZE_MM) -> bytes`:
- Generate the marker image via `cv2.aruco.generateImageMarker(ARUCO_DICTIONARY,
  ARUCO_MARKER_ID, marker_size_px)`.
- Composite it onto a white canvas with a quiet-zone border, plus a caption
  strip at the bottom reading something like *"Print at 100% scale - marker
  must measure {marker_size_mm}mm x {marker_size_mm}mm"* (use
  `cv2.putText`) — this is what stops users from printing it at the wrong
  scale via "fit to page."
- Encode as PNG (`cv2.imencode`) and return the bytes.

**5.2** — In `app.py`, add `GET /api/calibration-marker` that calls this and
returns it as `Response(content=png_bytes, media_type="image/png")`.

✅ Checkpoint: hitting `/api/calibration-marker` in a browser shows a clean,
scannable marker with the print-size caption legible.

---

## Phase 6 — Wire into `rules_engine.py`

**6.1** — Change `evaluate_all_rules()`'s signature: remove the
`package_height_cm=15.0, package_width_cm=10.0` defaults. Replace with
`package_height_cm: float | None = None, package_width_cm: float | None =
None, dimension_calibration_error: str | None = None`.

**6.2** — Inside `evaluate_all_rules()`: if both height and width are
provided, build `extracted_data["metadata"]` as before. Otherwise, set
`extracted_data["dimension_calibration_error"] = dimension_calibration_error
or "Package dimensions were not calibrated."` (no `metadata` key at all).

**6.3** — Inside `validate_label()`: keep the existing `if meta:` branch
exactly as-is (this is what `test_rules.py`/`run_pipeline.py` rely on,
calling `validate_label()` directly with metadata already built — don't
change this path). Add an `elif calibration_error:` branch that appends a
Rule 7(2) result with `"pass": False` and the calibration error as the
`"reason"`, instead of calling `calculate_pdp_area()`/`validate_pdp_font_height()`
at all.

**6.4** — Run `test_rules.py` and `run_pipeline.py` after this change —
they must still pass unmodified, since they call `validate_label()` directly
with metadata already present.

✅ Checkpoint: `evaluate_all_rules()` handles both the calibrated and
uncalibrated cases correctly; existing test scripts still pass untouched.

---

## Phase 7 — Wire into `app.py`

**7.1** — Import `calibrate_package_dimensions` from `calibration.py`.

**7.2** — In `POST /api/scan-image`: remove the `package_height_cm` and
`package_width_cm` Form parameters entirely. After reading `image_bytes` and
before/alongside the OCR call, run `calibration = calibrate_package_dimensions(image_bytes)`.

**7.3** — Pass the result into `evaluate_all_rules()`:
`package_height_cm=calibration.get("height_cm") if calibration["success"]
else None`, same for width, and `dimension_calibration_error=calibration.get("message")
if not calibration["success"] else None`.

**7.4** — Add `"dimension_calibration": calibration` to the JSON response
payload so the frontend can show calibration status.

✅ Checkpoint: `curl -X POST /api/scan-image -F "file=@photo.jpg"` (no
height/width fields sent at all) returns a response with a
`dimension_calibration` object showing either success + measured cm, or a
clear failure message.

---

## Phase 8 — Frontend UI updates

**8.1** — Remove the "Height (cm)" and "Width (cm)" manual number inputs
from the UI's "Dimensions" card entirely.

**8.2** — Replace that card's content with: short instructional text
("Package height & width are now measured automatically. Print the
calibration marker and place it flat next to the product, fully visible,
before photographing."), and a link/button to `/api/calibration-marker`
(open in new tab, so it can be printed).

**8.3** — Leave the "Detected Font Height (mm)" manual input as-is — that's
explicitly out of scope for this task (separate OCR-based work).

**8.4** — Update the JS `handleFormSubmit()` — stop appending
`package_height_cm`/`package_width_cm` to the `FormData`.

**8.5** — Add a calibration status card to the results panel: on success,
show something like *"Calibrated via marker ID {id}: {height}cm ×
{width}cm detected automatically"* in a green/success style; on failure,
show the calibration error message in an amber/warning style. Read this
from the new `dimension_calibration` field in the API response.

✅ Checkpoint: manually scan an image with no marker in frame — the amber
warning card should appear, and Rule 7(2) in the results table should show
the same message as its failure reason. Scan an image with a correctly
printed and placed marker — the card should turn green with plausible
detected dimensions.

---

## Phase 9 — Dependencies

**9.1** — Add `opencv-contrib-python-headless` and `numpy` to
`requirements.txt` (headless variant avoids pulling in GUI dependencies the
server doesn't need).

**9.2** — Check the Dockerfile's system packages — if `libgl1` and
`libglib2.0-0` aren't already present, add them (some OpenCV builds need
them even in headless mode, depending on the base image). Confirm the image
still builds after the change.

✅ Checkpoint: a clean `pip install -r requirements.txt` in a fresh venv
succeeds, and `import calibration` works from that venv.

---

## Phase 10 — End-to-end validation

**10.1** — Print the marker from `/api/calibration-marker` at **100% scale**
(no "fit to page"), verify with a ruler it's actually 40mm × 40mm.

**10.2** — Take a real photo: marker flat next to a real product package,
both fully visible, decent lighting. Run it through the full UI flow.
Confirm detected height/width are in the right ballpark (compare to a tape
measure).

**10.3** — Take a photo *without* the marker. Confirm the app fails
gracefully with the calibration message, not a crash or a silently wrong
7(2) verdict.

**10.4** — Confirm `test_rules.py` and `run_pipeline.py` still run clean
(Phase 6.4 covers this in code, this step is the final full-repo sanity
pass).

✅ Checkpoint: real photo → real, plausible measurement; no-marker photo →
honest failure; existing test scripts unaffected.

---

## Guardrails (apply throughout)

- **Never fabricate a dimension.** If calibration can't measure something,
  the Rule 7(2) check must fail explicitly with the reason — a wrong
  pass/fail verdict on a statutory compliance check is worse than an honest
  "couldn't measure."
- **Don't touch `ocr_engine.py` or `parser.py`** — out of scope for this
  task, owned elsewhere.
- **Don't change `validate_label()`'s existing behavior** when `metadata` is
  present — `test_rules.py` and `run_pipeline.py` depend on that path exactly
  as it is.
- Commit after each phase checkpoint, not once at the end — if something
  breaks, you want to know which phase did it.
- Keep `calibration.py` self-contained (image bytes in, structured dict out)
  — no direct FastAPI/Request dependencies inside it, so it stays testable
  standalone with plain function calls.
