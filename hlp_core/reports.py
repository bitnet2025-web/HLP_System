# ==============================
# HLP Management System - Report Generator
# ==============================
from fpdf import FPDF
from datetime import datetime
import os
from hlp_core.config import REPORTS_DIR, LOGO_PATH, HOTEL_NAME, APP_NAME

# ------------------------------
# PDF CLASS
# ------------------------------
class HLPReport(FPDF):
    def header(self):
        """Header with logo and title"""
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 10, 8, 25)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, f"{HOTEL_NAME}", ln=1, align="C")
        self.set_font("Helvetica", "", 12)
        self.cell(0, 10, f"{APP_NAME}", ln=1, align="C")
        self.ln(5)

    def footer(self):
        """Footer with page number"""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} / {{nb}}", align="C")

# ------------------------------
# REPORT GENERATOR FUNCTION
# ------------------------------
def generate_hlp_report(date_str, summary, highest_meter):
    """
    Generate the daily HLP report PDF
    :param date_str: date in 'YYYY-MM-DD'
    :param summary: list of tuples (meter_name, consumption, cost)
    :param highest_meter: tuple (meter_name, consumption, cost)
    """
    pdf = HLPReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ------------------------------
    # REPORT HEADER
    # ------------------------------
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"HLP REPORT - {date_str}", ln=1, align="C")
    pdf.ln(5)

    # ------------------------------
    # SUMMARY TABLE
    # ------------------------------
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(70, 10, "Meter Name", border=1, align="C")
    pdf.cell(50, 10, "Consumption", border=1, align="C")
    pdf.cell(50, 10, "Cost (Ksh)", border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 11)
    for meter_name, consumption, cost in summary:
        cost_str = f"{cost:,.2f}" if cost is not None else "-"
        pdf.cell(70, 8, meter_name, border=1)
        pdf.cell(50, 8, f"{consumption:,.2f}", border=1, align="R")
        pdf.cell(50, 8, cost_str, border=1, align="R")
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)

    # ------------------------------
    # HIGHEST METER SECTION
    # ------------------------------
    if highest_meter:
        pdf.cell(0, 10, f"Highest Consumption (excluding main meter):", ln=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0, 8,
            f"{highest_meter[0]} - {highest_meter[1]:,.2f} units",
            ln=1
        )

    pdf.ln(8)

    # ------------------------------
    # SIGNATURE LINE
    # ------------------------------
    pdf.cell(0, 15, "", ln=1)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 8, "Prepared by: Maintenance Technician ____________________", ln=1)
    pdf.cell(0, 8, "Approved by: Chief Engineer ____________________", ln=1)
    pdf.cell(0, 8, "Date: ____________________", ln=1)

    # ------------------------------
    # SAVE PDF
    # ------------------------------
    filename = f"HLP_Report_{date_str.replace('-', '_')}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    pdf.output(filepath)

    print(f"✅ Report generated successfully: {filepath}")
    return filepath
