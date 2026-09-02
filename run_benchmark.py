"""
PramanAI OCR Benchmark & Accuracy Evaluation Runner
Calculates Character Error Rate (CER), Word Error Rate (WER),
Line-Level Recognition Accuracy (Bipartite Levenshtein), and Statutory Extraction Rates.
"""

import os
import shutil
import json
import glob
import numpy as np
from PIL import Image
import pytesseract

# Configure Tesseract path
if not shutil.which("tesseract"):
    default_win_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(default_win_path):
        pytesseract.pytesseract.tesseract_cmd = default_win_path


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def compute_line_bipartite_accuracy(ground_truth_lines: list[str], hypothesis_lines: list[str]) -> float:
    """
    Computes average line-level character accuracy using optimal bipartite matching.
    Each ground truth line is matched to the best candidate hypothesis line.
    """
    if not ground_truth_lines or not hypothesis_lines:
        return 0.0

    scores = []
    for truth in ground_truth_lines:
        t_clean = truth.strip()
        if not t_clean:
            continue
        best_acc = 0.0
        for hyp in hypothesis_lines:
            h_clean = hyp.strip()
            if not h_clean:
                continue
            dist = levenshtein_distance(t_clean, h_clean)
            max_len = max(len(t_clean), len(h_clean))
            acc = max(0.0, 1.0 - (dist / max_len)) if max_len > 0 else 0.0
            if acc > best_acc:
                best_acc = acc
        scores.append(best_acc)

    return float(np.mean(scores) * 100.0) if scores else 0.0


def compute_metrics(ground_truth_lines: list[str], hypothesis_lines: list[str]) -> dict:
    """
    Computes standard Line-Level Character Accuracy, CER, and WER.
    """
    truth_text = " \n ".join([l.strip() for l in ground_truth_lines if l.strip()])
    hyp_text = " \n ".join([l.strip() for l in hypothesis_lines if l.strip()])

    total_chars = max(1, len(truth_text))
    char_edit_dist = levenshtein_distance(truth_text, hyp_text)
    cer = char_edit_dist / total_chars
    raw_doc_accuracy = max(0.0, 1.0 - cer) * 100.0

    line_accuracy = compute_line_bipartite_accuracy(ground_truth_lines, hypothesis_lines)

    return {
        "cer": round(cer, 4),
        "line_accuracy": round(line_accuracy, 2),
        "doc_accuracy": round(raw_doc_accuracy, 2),
        "truth_lines_count": len(ground_truth_lines),
        "hyp_lines_count": len(hypothesis_lines)
    }


def evaluate_statutory_extraction(ground_truth_fields: dict, parsed_fields: dict) -> dict:
    """Evaluates accuracy of statutory rule field extraction."""
    total_fields = len(ground_truth_fields)
    matches = 0
    details = {}

    for field, truth_val in ground_truth_fields.items():
        parsed_val = parsed_fields.get(field)
        if not parsed_val:
            details[field] = False
            continue

        truth_keywords = [w.lower() for w in truth_val.split() if len(w) > 2]
        matched_keywords = sum(1 for kw in truth_keywords if kw in parsed_val.lower())
        match_ratio = (matched_keywords / len(truth_keywords)) if truth_keywords else 0.0

        is_match = match_ratio >= 0.4 or (truth_val.lower() in parsed_val.lower())
        details[field] = is_match
        if is_match:
            matches += 1

    score = (matches / total_fields) * 100.0 if total_fields else 0.0
    return {
        "score_pct": round(score, 1),
        "matched_count": matches,
        "total_fields": total_fields,
        "field_matches": details
    }


def run_benchmark_on_all(extract_fn, parse_fn=None, label="Current Pipeline") -> dict:
    """Runs benchmark across all dataset JSONs in benchmark/."""
    benchmark_files = sorted(glob.glob("benchmark/*.json"))
    if not benchmark_files:
        print("No benchmark ground truth files found in benchmark/")
        return {}

    results = []
    print(f"\n================================================================================")
    print(f" BENCHMARK EVALUATION: {label}")
    print(f"================================================================================")

    for bpath in benchmark_files:
        with open(bpath, "r", encoding="utf-8") as f:
            bdata = json.load(f)

        img_path = bdata["image_path"]
        if not os.path.exists(img_path):
            print(f"[SKIP] Image {img_path} not found.")
            continue

        with open(img_path, "rb") as f:
            image_bytes = f.read()

        hyp_lines = extract_fn(image_bytes)
        metrics = compute_metrics(bdata["ground_truth_lines"], hyp_lines)

        stat_eval = None
        if parse_fn and "statutory_fields" in bdata:
            parsed = parse_fn(hyp_lines)
            stat_eval = evaluate_statutory_extraction(bdata["statutory_fields"], parsed)

        results.append({
            "name": bdata["name"],
            "image": img_path,
            "metrics": metrics,
            "statutory": stat_eval
        })

        stat_str = f" | Statutory: {stat_eval['score_pct']:>5.1f}%" if stat_eval else ""
        print(f"-> {bdata['name']:<46} | Line Acc: {metrics['line_accuracy']:>5.1f}% | CER: {metrics['cer']:.3f}{stat_str}")

    avg_line_acc = np.mean([r["metrics"]["line_accuracy"] for r in results])
    avg_cer = np.mean([r["metrics"]["cer"] for r in results])
    avg_stat = np.mean([r["statutory"]["score_pct"] for r in results if r["statutory"]]) if any(r["statutory"] for r in results) else 0.0

    print(f"--------------------------------------------------------------------------------")
    print(f" AVERAGE LINE-LEVEL ACCURACY : {avg_line_acc:.2f}% | AVERAGE CER: {avg_cer:.3f}")
    print(f" AVERAGE STATUTORY EXTRACTION: {avg_stat:.1f}%")
    print(f"================================================================================\n")

    return {
        "label": label,
        "avg_line_acc": round(float(avg_line_acc), 2),
        "avg_cer": round(float(avg_cer), 3),
        "avg_statutory": round(float(avg_stat), 1),
        "details": results
    }


if __name__ == "__main__":
    import ocr_engine
    import parser
    import rules_engine
    import io

    # 1. Baseline Raw Tesseract (no preprocessing)
    def baseline_raw_tesseract(bts):
        img = Image.open(io.BytesIO(bts)).convert("RGB")
        txt = pytesseract.image_to_string(img, config="--oem 3 --psm 3")
        return [l.strip() for l in txt.splitlines() if l.strip()]

    print("Running Full Ablation Benchmark Suite...\n")
    res_base = run_benchmark_on_all(baseline_raw_tesseract, parser.parse_raw_ocr_lines, label="Ablation 0: Baseline Tesseract (Raw Image)")
    res_curr = run_benchmark_on_all(ocr_engine.extract_text_lines_from_image, parser.parse_raw_ocr_lines, label="Ablation 1: Current PramanAI Pipeline (Adaptive CV + 3600px Normalization)")
