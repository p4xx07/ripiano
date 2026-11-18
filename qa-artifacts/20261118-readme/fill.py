"""Fill a fresh Ripiano stack with the synthetic showcase documents through the public API."""
import sys, time
from pathlib import Path
import httpx

origin, setup_key, password, folder = sys.argv[1:5]
client = httpx.Client(base_url=origin, timeout=60)
client.get("/api/session")
h = lambda: {"X-CSRFToken": client.cookies.get("csrftoken", ""), "Referer": origin + "/"}
assert client.post("/api/setup", json={"setup_key": setup_key, "username": "giulia", "password": password}, headers=h()).status_code == 201
assert client.post("/api/session", json={"username": "giulia", "password": password}, headers=h()).status_code == 200

def make(path, name, **extra):
    response = client.post(path, json={"name": name, **extra}, headers=h())
    assert response.status_code == 201, response.text
    return response.json()["id"]

tags = {name: make("/api/tags", name, color=color) for name, color in
        (("Casa", "#3b7a57"), ("Bollette", "#c46a2c"), ("Auto", "#3a6ea5"), ("Lavoro", "#7a4fa3"), ("Salute", "#b8434d"))}
senders = {name: make("/api/correspondents", name) for name in
           ("Luce Chiara Energia", "Comune di Valverde", "Studio Notarile Bianchi", "Assicurazioni Serene", "Northwind Analytics", "Farmacia San Marco")}
types = {name: make("/api/document-types", name) for name in ("Bolletta", "Avviso", "Contratto", "Polizza", "Busta paga", "Ricevuta")}
plan = [
    ("ricevuta-farmacia", "Ricevuta farmacia", "2026-11-09", "Farmacia San Marco", "Ricevuta", ["Salute"]),
    ("payslip-october", "Payslip October 2026", "2026-10-27", "Northwind Analytics", "Busta paga", ["Lavoro"]),
    ("polizza-auto", "Polizza RC auto 2026–2027", "2026-04-15", "Assicurazioni Serene", "Polizza", ["Auto"]),
    ("contratto-locazione", "Contratto di locazione", "2026-03-01", "Studio Notarile Bianchi", "Contratto", ["Casa"]),
    ("avviso-tari-2026", "Avviso TARI 2026", "2026-10-02", "Comune di Valverde", "Avviso", ["Casa", "Bollette"]),
    ("bolletta-luce-ottobre", "Bolletta luce ottobre 2026", "2026-11-14", "Luce Chiara Energia", "Bolletta", ["Casa", "Bollette"]),
]
ids = {}
for file, *_ in plan:
    content = (Path(folder) / f"{file}.png").read_bytes()
    response = client.post("/api/documents", files={"document": (f"{file}.png", content, "image/png")}, headers=h())
    assert response.status_code == 202, response.text
    ids[file] = response.json()["id"]
    time.sleep(1.5)  # distinct "added" times, newest last
for _ in range(120):
    if all(client.get(f"/api/documents/{item}").json()["status"] == "ready" for item in ids.values()):
        break
    time.sleep(2)
for file, title, day, sender, kind, tag_names in plan:
    response = client.patch(f"/api/documents/{ids[file]}", json={"title": title, "document_date": day, "correspondent_id": senders[sender],
                            "document_type_id": types[kind], "tags": [tags[name] for name in tag_names]}, headers=h())
    assert response.status_code == 200, response.text
shelf = make("/api/locations", "Studio – libreria")
box = make("/api/locations", "Raccoglitore Casa", parent_id=shelf)
for file in ("contratto-locazione", "avviso-tari-2026"):
    assert client.post(f"/api/documents/{ids[file]}/copies", json={"location_id": box}, headers=h()).status_code == 201
print("filled", len(ids))
