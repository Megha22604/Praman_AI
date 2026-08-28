import re


def clean_text(raw_text):
    """Cleans up raw OCR text strings."""
    if not raw_text:
        return ""
    return " ".join(raw_text.split()).strip()


def parse_raw_ocr_lines(lines):
    """
    Parses a raw list of detected text lines from an OCR engine
    and extracts standard LMPC fields.
    """
    parsed = {
        "mrp": None,
        "manufacturer": None,
        "net_quantity": None,
        "mfg_date": None,
        "consumer_care": None,
        "country_of_origin": None,
        "unit_sale_price": None,
    }

    full_text = " \n ".join([clean_text(line) for line in lines if line])

    for line in lines:
        cleaned_line = clean_text(line)
        line_lower = cleaned_line.lower()

        # 1. MRP Extraction
        if any(sym in line_lower for sym in ["mrp", "rs.", "rs ", "₹", "inr"]):
            if not parsed["mrp"] and any(char.isdigit() for char in cleaned_line):
                parsed["mrp"] = cleaned_line

        # 2. Net Quantity Extraction
        if any(keyword in line_lower for keyword in ["net wt", "net weight", "net qty", "net quantity", "weight:"]):
            parsed["net_quantity"] = cleaned_line
        elif not parsed["net_quantity"]:
            # Pattern check if keyword is missing but '500 g' or '1 kg' is found standalone
            match = re.search(r"\b\d+(?:\.\d+)?\s*(g|gm|kg|ml|l|ltr|pcs|count)\b", line_lower)
            if match and "per" not in line_lower and "/" not in line_lower:
                parsed["net_quantity"] = cleaned_line

        # 3. Unit Sale Price (USP)
        if any(kw in line_lower for kw in ["usp", "unit sale price", "/ g", "/g", "/ ml", "/ml", "/ kg", "/kg", "per g", "per ml"]):
            if any(char.isdigit() for char in cleaned_line):
                parsed["unit_sale_price"] = cleaned_line

        # 4. Manufacturing / Packaging Date
        if any(kw in line_lower for kw in ["mfg", "pkd", "packed", "date", "batch"]):
            date_match = re.search(r"\b(0[1-9]|1[0-2]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\/\-\s,]+(20\d{2}|\d{2})\b", line_lower)
            if date_match:
                parsed["mfg_date"] = cleaned_line

        # 5. Manufacturer / Packer Details
        if any(kw in line_lower for kw in ["mfd by", "mfg by", "manufactured by", "packed by", "pkd by", "marketed by"]):
            parsed["manufacturer"] = cleaned_line

        # 6. Consumer Care Contact Details
        if any(kw in line_lower for kw in ["consumer care", "customer care", "toll free", "helpdesk", "feedback", "@", "care@"]):
            parsed["consumer_care"] = cleaned_line

        # 7. Country of Origin
        if any(kw in line_lower for kw in ["country of origin", "made in", "origin:"]):
            parsed["country_of_origin"] = cleaned_line
        elif "made in india" in line_lower:
            parsed["country_of_origin"] = "India"

    return parsed