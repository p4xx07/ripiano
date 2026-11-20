"""Write small, fictional household documents as text PDFs (standard library only).

Every company, person, and address below is invented for the Ripiano demo.
Usage: python3 make_docs.py OUTPUT_FOLDER
"""
import sys
from pathlib import Path

HOLDER = "Alex Morgan, 14 Juniper Lane, Lakeford"

# file: (sender, sender line, brand colour, title, metadata rows, line items, total, note)
DOCS = {
    "electricity-bill-2026-10": ("Northwind Energy", "Customer care 0800 555 0142 - northwind-energy.example", (0.11, 0.30, 0.24),
        "Electricity bill - October 2026",
        [("Account holder", HOLDER), ("Account number", "NWE-4471-2290"), ("Billing period", "1 - 31 October 2026"), ("Issue date", "12 November 2026"), ("Due date", "5 December 2026")],
        [("Energy used: 212 kWh at 0.24 EUR", "50.88"), ("Standing charge: 31 days", "9.30"), ("Network and system costs", "4.12")],
        ("Total to pay", "64.30 EUR"), "Paid by direct debit on the due date. Thank you for choosing renewable energy."),
    "water-bill-2026-q3": ("Clearwater Water Services", "Lakeford district - clearwater.example", (0.12, 0.38, 0.62),
        "Water bill - July to September 2026",
        [("Account holder", HOLDER), ("Meter number", "CW-883104"), ("Reading", "1,482 m3 (actual)"), ("Issue date", "5 October 2026"), ("Due date", "30 October 2026")],
        [("Water supply: 24 m3", "38.40"), ("Wastewater", "21.60"), ("Fixed quarterly charge", "12.00")],
        ("Total to pay", "72.00 EUR"), "Your average daily use is 261 litres, 6% lower than last year."),
    "internet-invoice-2026-11": ("Brightline Fibre", "Home broadband - brightline.example", (0.42, 0.25, 0.60),
        "Internet invoice - November 2026",
        [("Customer", HOLDER), ("Invoice number", "BF-2026-118204"), ("Plan", "Fibre 1 Gbit/s, unlimited"), ("Invoice date", "3 November 2026"), ("Due date", "20 November 2026")],
        [("Monthly plan", "29.90"), ("Router rental", "3.00")],
        ("Total", "32.90 EUR"), "Charged to the card ending 4417."),
    "lease-agreement": ("Elmwood Lettings", "Residential lettings - Lakeford", (0.36, 0.28, 0.18),
        "Residential lease agreement",
        [("Tenant", "Alex Morgan"), ("Landlord", "Jordan Ellis, through Elmwood Lettings"), ("Property", "14 Juniper Lane, flat 4, Lakeford"), ("Start date", "1 March 2026"), ("Term", "4 years, renewable"), ("Monthly rent", "850.00 EUR, due on the 1st"), ("Deposit", "2,550.00 EUR")],
        [], None, "Signed by both parties. The original paper copy carries the registration stamp."),
    "home-insurance-policy": ("Harbor Mutual Insurance", "Home and contents cover", (0.13, 0.27, 0.45),
        "Home insurance policy 2026-2027",
        [("Policyholder", HOLDER), ("Policy number", "HM-HOME-552918"), ("Cover", "Buildings and contents, 60,000 EUR"), ("Period", "18 June 2026 - 17 June 2027"), ("Excess", "150 EUR per claim")],
        [("Annual premium", "236.00"), ("Legal expenses add-on", "24.00")],
        ("Total premium", "260.00 EUR"), "Keep this schedule with your policy wording. Claims line: 0800 555 0199."),
    "car-insurance-certificate": ("Harbor Mutual Insurance", "Motor insurance", (0.13, 0.27, 0.45),
        "Car insurance certificate",
        [("Policyholder", "Alex Morgan"), ("Policy number", "HM-CAR-310577"), ("Vehicle", "Compact hatchback, plate LK-482-MN"), ("Valid", "15 April 2026 - 14 April 2027"), ("Cover", "Third party, fire and theft")],
        [("Annual premium", "412.50")],
        ("Total premium", "412.50 EUR"), "Roadside assistance is included. Keep this certificate in the vehicle."),
    "payslip-2026-10": ("Bluepeak Software Ltd", "Payroll department", (0.20, 0.33, 0.55),
        "Payslip - October 2026",
        [("Employee", "Alex Morgan"), ("Role", "Data analyst"), ("Employee number", "BP-0418"), ("Pay date", "30 October 2026"), ("Holiday balance", "14 days")],
        [("Gross salary", "3,450.00"), ("Income tax", "-702.40"), ("Social contributions", "-310.00")],
        ("Net pay", "2,437.60 EUR"), "Paid by bank transfer."),
    "payslip-2026-09": ("Bluepeak Software Ltd", "Payroll department", (0.20, 0.33, 0.55),
        "Payslip - September 2026",
        [("Employee", "Alex Morgan"), ("Role", "Data analyst"), ("Employee number", "BP-0418"), ("Pay date", "30 September 2026"), ("Holiday balance", "16 days")],
        [("Gross salary", "3,450.00"), ("Income tax", "-702.40"), ("Social contributions", "-310.00")],
        ("Net pay", "2,437.60 EUR"), "Paid by bank transfer."),
    "blood-test-results": ("Lakeford Family Clinic", "General practice and laboratory", (0.62, 0.20, 0.25),
        "Blood test results",
        [("Patient", "Alex Morgan"), ("Requested by", "Dr. Priya Nolan"), ("Sample taken", "22 September 2026"), ("Report date", "24 September 2026")],
        [("Haemoglobin: 14.2 g/dL", "normal"), ("Total cholesterol: 182 mg/dL", "normal"), ("Vitamin D: 24 ng/mL", "low")],
        None, "Vitamin D slightly low; repeat in three months. No other action needed."),
    "pharmacy-receipt": ("Greenleaf Pharmacy", "Market Square, Lakeford", (0.18, 0.48, 0.30),
        "Pharmacy receipt",
        [("Date", "8 November 2026, 18:42"), ("Receipt number", "GL-77310")],
        [("Vitamin D3 drops", "9.90"), ("Allergy tablets", "7.40"), ("Plasters", "6.50")],
        ("Total paid", "23.80 EUR"), "Medical expenses: keep this receipt for your tax return."),
    "car-service-invoice": ("Lakeford Auto Care", "Servicing and repairs", (0.55, 0.32, 0.10),
        "Car service invoice",
        [("Customer", HOLDER), ("Vehicle", "Compact hatchback, plate LK-482-MN"), ("Mileage", "48,210 km"), ("Date", "14 August 2026"), ("Invoice number", "LAC-2026-0931")],
        [("Annual service", "145.00"), ("Front brake pads", "88.00"), ("Wiper blades", "22.00")],
        ("Total", "255.00 EUR"), "Next service due at 63,000 km or August 2027."),
    "laptop-receipt-warranty": ("Lumen Electronics", "Online store - lumen-electronics.example", (0.25, 0.25, 0.28),
        "Laptop receipt and warranty",
        [("Customer", "Alex Morgan"), ("Order number", "LE-5520193"), ("Product", "14-inch laptop, 16 GB, 512 GB SSD"), ("Purchase date", "2 July 2026"), ("Warranty until", "2 July 2028")],
        [("Laptop", "899.00"), ("Sleeve", "19.00")],
        ("Total paid", "918.00 EUR"), "Bring this receipt for warranty repairs."),
    "waste-tax-2026": ("City of Lakeford", "Revenue office", (0.30, 0.30, 0.30),
        "Waste collection tax 2026",
        [("Taxpayer", HOLDER), ("Property", "85 m2, 1 occupant"), ("Notice date", "2 October 2026"), ("First instalment", "16 December 2026"), ("Second instalment", "16 June 2027")],
        [("Annual waste collection charge", "312.00")],
        ("Amount due", "312.00 EUR"), "Pay online with the reference LKF-TX-26-00418."),
}


def text(x, y, size, value, bold=False, rgb=(0, 0, 0)):
    data = value.encode("cp1252").hex()
    return f"{rgb[0]:.2f} {rgb[1]:.2f} {rgb[2]:.2f} rg BT /{'F2' if bold else 'F1'} {size} Tf {x} {y} Td <{data}> Tj ET\n"


def width(value, size):
    return len(value) * size * 0.5  # Helvetica average, enough for right alignment of numbers


def page(sender, line, colour, title, meta, items, total, note):
    out = f"{colour[0]} {colour[1]} {colour[2]} rg 0 752 595 90 re f\n"
    out += text(50, 800, 22, sender, True, (1, 1, 1)) + text(50, 776, 10, line, rgb=(1, 1, 1))
    out += text(50, 700, 20, title, True)
    y = 660
    for label, value in meta:
        out += text(50, y, 10, label, True, (0.4, 0.4, 0.4)) + text(190, y, 11, value)
        y -= 22
    if items:
        y -= 18
        out += f"0.85 0.85 0.85 RG 1 w 50 {y + 14} m 545 {y + 14} l S\n"
        out += text(50, y, 10, "Description", True, (0.4, 0.4, 0.4)) + text(470, y, 10, "Amount" if total else "Result", True, (0.4, 0.4, 0.4))
        for description, amount in items:
            y -= 24
            out += text(50, y, 11, description) + text(int(545 - width(amount, 11)), y, 11, amount)
        out += f"0.85 0.85 0.85 RG 50 {y - 10} m 545 {y - 10} l S\n"
    if total:
        y -= 50
        out += f"0.95 0.95 0.95 rg 330 {y - 12} 215 36 re f\n"
        out += text(342, y, 12, total[0], True) + text(int(533 - width(total[1], 13)), y, 13, total[1], True)
    out += text(50, y - 60, 11, note)
    out += text(50, 40, 8, "Fictional sample document generated for the Ripiano demo. Names, companies, and addresses are invented.", rgb=(0.5, 0.5, 0.5))
    return out


def pdf(content):
    stream = content.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    body, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return body


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in DOCS.items():
        (out / f"{name}.pdf").write_bytes(pdf(page(*spec)))
    print("made", len(DOCS))
