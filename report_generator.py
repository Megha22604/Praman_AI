from fpdf import FPDF
from datetime import datetime


def sanitize_text(text: str) -> str:
    """Replaces Unicode characters like ₹ and cleans strings for core PDF fonts."""
    if not text:
        return ""
    text = str(text).replace("₹", "Rs.").replace("’", "'").replace("“", '"').replace("”", '"')
    return text.encode("latin-1", "replace").decode("latin-1")


# Verbatim statutory provisions under Legal Metrology (Packaged Commodities) Rules, 2011
STATUTORY_RULES_TEXT = [
    (
        "Rule 6(1)(a) - Manufacturer / Packer / Importer Details",
        "Every package shall bear the name and complete address of the manufacturer, or where the manufacturer is not the packer, the name and address of the manufacturer and packer, and in case of imported packages, the name and address of the importer."
    ),
    (
        "Rule 6(1)(aa) - Country of Origin",
        "The name of the country of origin or manufacture or assembly in case of imported products shall be mentioned on the package."
    ),
    (
        "Rule 6(1)(c) - Net Quantity Declaration",
        "The net quantity, in terms of the standard unit of weight or measure, of the commodity contained in the package shall be declared plainly and conspicuously in accordance with the prescribed units (g, kg, ml, l, or number)."
    ),
    (
        "Rule 6(1)(d) - Date of Manufacture / Packing / Import",
        "The month and year in which the commodity is manufactured or packed or imported shall be clearly indicated on the label of the pre-packaged commodity."
    ),
    (
        "Rule 6(1)(e) - Maximum Retail Price (MRP)",
        "The retail sale price of the package shall be stated in the form of Maximum Retail Price (MRP) Rs. ... / INR ... inclusive of all taxes, clearly indicating that it is inclusive of all taxes."
    ),
    (
        "Rule 6(2) - Consumer Care Details",
        "Every package shall bear the name, address, telephone number, and e-mail address of the person or the office who can be contacted in case of consumer complaints."
    ),
    (
        "Rule 6(11) - Unit Sale Price (USP)",
        "The unit sale price shall be declared on the package in Rupees (rounded off to the nearest two decimal places) per gram/kilogram or per milliliter/liter where the net quantity is more than one unit or specified thresholds."
    ),
    (
        "Rule 7(2) & Table-I - Minimum Font Height on Principal Display Panel (PDP)",
        "The minimum height of numerals and letters for net quantity declarations and statutory mandatory statements shall correspond strictly to the Principal Display Panel (PDP) area as prescribed in Table-I (e.g., minimum 2.5 mm for PDP area between 100 cm2 to 500 cm2)."
    ),
]


class LegalNoticePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 7, "GOVERNMENT OF INDIA - LEGAL METROLOGY ENFORCEMENT", align="C")
        self.ln(5)
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "Packaged Commodities Rules, 2011 - Digital Inspection Notice", align="C")
        self.ln(7)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} | Pramand_AI Regulatory Compliance Intelligence", align="C")


def generate_pdf_report(compliance_data, output_path="inspection_report.pdf"):
    pdf = LegalNoticePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 1. Summary Header
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"Inspection Date: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    pdf.ln(5)

    report = compliance_data.get("compliance_report", {})
    is_compliant = report.get("compliant", False)
    score_text = sanitize_text(report.get("score", "N/A"))

    # Status Banner
    pdf.set_font("Helvetica", "B", 10)
    if is_compliant:
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 6, f"Overall Status: FULLY COMPLIANT ({score_text})")
    else:
        pdf.set_text_color(185, 28, 28)
        pdf.cell(0, 6, f"Overall Status: NON-COMPLIANCE DETECTED ({score_text})")
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(7)

    # 2. Findings Table Header
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(240, 244, 240)
    pdf.cell(40, 6, "Field", border=1, fill=True)
    pdf.cell(26, 6, "Rule Cited", border=1, fill=True)
    pdf.cell(18, 6, "Status", border=1, fill=True)
    pdf.cell(106, 6, "Finding / Reason", border=1, fill=True)
    pdf.ln(6)

    # 3. Table Rows
    pdf.set_font("Helvetica", "", 8)
    for row in report.get("results", []):
        status_text = "PASS" if row["pass"] else "FAIL"

        pdf.cell(40, 6, sanitize_text(row.get("field", "")), border=1)
        pdf.cell(26, 6, sanitize_text(row.get("rule", "")), border=1)

        # Status text color
        if row["pass"]:
            pdf.set_text_color(22, 101, 52)
        else:
            pdf.set_text_color(185, 28, 28)
        pdf.cell(18, 6, status_text, border=1)

        pdf.set_text_color(0, 0, 0)
        raw_reason = sanitize_text(str(row.get("reason", "")))
        clean_reason = (raw_reason[:68] + "..") if len(raw_reason) > 70 else raw_reason
        pdf.cell(106, 6, clean_reason, border=1)
        pdf.ln(6)

    # 4. Statutory Rules Annexure (Word-by-Word Reference)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 235, 230)
    pdf.cell(0, 5.5, "STATUTORY REFERENCE ANNEXURE - PACKAGED COMMODITIES RULES, 2011", border=1, fill=True, align="L")
    pdf.ln(7)

    for rule_title, rule_body in STATUTORY_RULES_TEXT:
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(0, 4, rule_title)
        pdf.ln(3.5)
        pdf.set_font("Helvetica", "", 7)
        pdf.multi_cell(0, 3.5, rule_body)
        pdf.ln(1.5)

    # 5. Statutory Closing Disclaimer
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 6.5)
    pdf.multi_cell(0, 3, "Notice: This automated inspection report is generated pursuant to the Legal Metrology Act, 2009 and the Legal Metrology (Packaged Commodities) Rules, 2011. Formal compounding notices and penalty determinations remain subject to physical evidence verification by designated Legal Metrology Inspectors.")

    pdf.output(output_path)
    return output_path