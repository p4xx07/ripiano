"""File the fictional demo documents into an empty Ripiano account through the public API.

Usage: uv run --with httpx python fill.py ORIGIN USERNAME DOCS_FOLDER   (password in RIPIANO_DEMO_PASSWORD)
"""
import os
import sys
import time
from pathlib import Path

import httpx

origin, username, folder = sys.argv[1:4]
client = httpx.Client(base_url=origin, timeout=60)
client.get("/api/session")
h = lambda: {"X-CSRFToken": client.cookies.get("csrftoken", ""), "Referer": origin + "/"}
response = client.post("/api/session", json={"username": username, "password": os.environ["RIPIANO_DEMO_PASSWORD"]}, headers=h())
assert response.status_code == 200, response.text


def make(path, name, **extra):
    response = client.post(path, json={"name": name, **extra}, headers=h())
    assert response.status_code == 201, response.text
    return response.json()["id"]


# New accounts start with the starter tags; reuse any tag that already exists.
existing_tags = {tag["name"]: tag["id"] for tag in client.get("/api/tags").json()["tags"]}
tags = {name: existing_tags.get(name) or make("/api/tags", name, color=color) for name, color in (
    ("Home", "#3b7a57"), ("Utilities", "#c46a2c"), ("Insurance", "#3a6ea5"), ("Car", "#5b6b7a"),
    ("Work", "#7a4fa3"), ("Health", "#b8434d"), ("Warranty", "#8a7a2e"), ("Taxes", "#2e7f86"))}
senders = {name: make("/api/correspondents", name) for name in (
    "Northwind Energy", "Clearwater Water Services", "Brightline Fibre", "Elmwood Lettings", "Harbor Mutual Insurance",
    "Bluepeak Software", "Lakeford Family Clinic", "Greenleaf Pharmacy", "Lakeford Auto Care", "Lumen Electronics", "City of Lakeford")}
types = {name: make("/api/document-types", name) for name in (
    "Bill", "Invoice", "Contract", "Policy", "Payslip", "Medical report", "Receipt", "Tax notice")}

# Uploaded oldest first so the newest document is also the most recently added.
plan = [
    ("lease-agreement", "Apartment lease agreement", "2026-03-01", "Elmwood Lettings", "Contract", ["Home"]),
    ("car-insurance-certificate", "Car insurance certificate 2026-2027", "2026-04-15", "Harbor Mutual Insurance", "Policy", ["Car", "Insurance"]),
    ("home-insurance-policy", "Home insurance policy 2026-2027", "2026-06-18", "Harbor Mutual Insurance", "Policy", ["Home", "Insurance"]),
    ("laptop-receipt-warranty", "Laptop receipt and warranty", "2026-07-02", "Lumen Electronics", "Receipt", ["Warranty"]),
    ("car-service-invoice", "Car service at 48,000 km", "2026-08-14", "Lakeford Auto Care", "Invoice", ["Car"]),
    ("blood-test-results", "Blood test results", "2026-09-24", "Lakeford Family Clinic", "Medical report", ["Health"]),
    ("payslip-2026-09", "Payslip September 2026", "2026-09-30", "Bluepeak Software", "Payslip", ["Work"]),
    ("waste-tax-2026", "Waste collection tax 2026", "2026-10-02", "City of Lakeford", "Tax notice", ["Home", "Taxes"]),
    ("water-bill-2026-q3", "Water bill July-September 2026", "2026-10-05", "Clearwater Water Services", "Bill", ["Home", "Utilities"]),
    ("payslip-2026-10", "Payslip October 2026", "2026-10-30", "Bluepeak Software", "Payslip", ["Work"]),
    ("internet-invoice-2026-11", "Internet invoice November 2026", "2026-11-03", "Brightline Fibre", "Invoice", ["Home", "Utilities"]),
    ("pharmacy-receipt", "Pharmacy receipt", "2026-11-08", "Greenleaf Pharmacy", "Receipt", ["Health", "Taxes"]),
    ("electricity-bill-2026-10", "Electricity bill October 2026", "2026-11-12", "Northwind Energy", "Bill", ["Home", "Utilities"]),
]
ids = {}
for file, *_ in plan:
    content = (Path(folder) / f"{file}.pdf").read_bytes()
    response = client.post("/api/documents", files={"document": (f"{file}.pdf", content, "application/pdf")}, headers=h())
    assert response.status_code == 202, response.text
    ids[file] = response.json()["id"]
    time.sleep(1.5)  # distinct "added" times
for _ in range(180):
    if all(client.get(f"/api/documents/{item}").json()["status"] == "ready" for item in ids.values()):
        break
    time.sleep(2)
for file, title, day, sender, kind, tag_names in plan:
    response = client.patch(f"/api/documents/{ids[file]}", json={
        "title": title, "document_date": day, "correspondent_id": senders[sender],
        "document_type_id": types[kind], "tags": [tags[name] for name in tag_names]}, headers=h())
    assert response.status_code == 200, response.text

bookcase = make("/api/locations", "Study bookcase")
home_folder = make("/api/locations", "Blue folder: Home", parent_id=bookcase)
cabinet = make("/api/locations", "Hall cabinet")
car_box = make("/api/locations", "Car papers box", parent_id=cabinet)
for file, location in (("lease-agreement", home_folder), ("home-insurance-policy", home_folder), ("car-insurance-certificate", car_box)):
    response = client.post(f"/api/documents/{ids[file]}/copies", json={"location_id": location}, headers=h())
    assert response.status_code == 201, response.text
print("filled", len(ids))
