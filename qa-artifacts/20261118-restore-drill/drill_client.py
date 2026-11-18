"""Drive a Ripiano stack over HTTP for the restore drill. Usage: client.py <origin> <command> [args]"""
import hashlib, json, sys, time
from pathlib import Path
import httpx

origin, command, *args = sys.argv[1:]
state = Path(__file__).with_name("state.json")
data = json.loads(state.read_text()) if state.exists() else {}
client = httpx.Client(base_url=origin, timeout=60)
client.get("/api/session")

def headers():
    return {"X-CSRFToken": client.cookies.get("csrftoken", ""), "Referer": origin + "/"}

def login():
    response = client.post("/api/session", json={"username": "drill-owner", "password": data["password"]}, headers=headers())
    assert response.status_code == 200, response.text

if command == "setup":
    data["password"] = args[1]
    response = client.post("/api/setup", json={"setup_key": args[0], "username": "drill-owner", "password": data["password"]}, headers=headers())
    assert response.status_code == 201, response.text
    login()
    fixtures = Path(args[2])
    data["docs"] = {}
    for name in ("three-pages.pdf", "judge.png", "office-letter.docx", "email-notice.eml"):
        content = (fixtures / name).read_bytes()
        response = client.post("/api/documents", files={"document": (name, content)}, headers=headers())
        assert response.status_code == 202, response.text
        data["docs"][response.json()["id"]] = hashlib.sha256(content).hexdigest()
    tag = client.post("/api/tags", json={"name": "Drill tag"}, headers=headers()).json()
    first = next(iter(data["docs"]))
    for _ in range(90):
        statuses = [client.get(f"/api/documents/{item}").json()["status"] for item in data["docs"]]
        if all(item in ("ready", "failed") for item in statuses):
            break
        time.sleep(2)
    print("statuses", statuses)
    assert client.patch(f"/api/documents/{first}", json={"tags": [tag["id"]], "title": "Drill lease"}, headers=headers()).status_code == 200
    data["first"] = first
    response = client.post("/api/backups", headers=headers())
    assert response.status_code == 202, response.text
    run = response.json()["id"]
    for _ in range(90):
        runs = {item["id"]: item for item in client.get("/api/backups").json()["runs"]}
        if runs[run]["status"] in ("complete", "failed"):
            break
        time.sleep(2)
    print("backup", runs[run]["status"], runs[run]["snapshot_name"], runs[run]["error"])
    data["snapshot"] = runs[run]["snapshot_name"]
    state.write_text(json.dumps(data))
elif command == "verify":
    login()
    documents = client.get("/api/documents").json()["documents"]
    print("documents", len(documents), sorted(item["title"] for item in documents))
    ok = True
    for item, digest in data["docs"].items():
        response = client.get(f"/api/documents/{item}/original")
        same = response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == digest
        ok &= same
        print(item[:8], response.status_code, "checksum ok" if same else "MISMATCH")
    detail = client.get(f"/api/documents/{data['first']}").json()
    print("first:", detail["title"], [tag["name"] for tag in detail["tags"]])
    found = client.get("/api/documents", params={"q": "tag:Drill"}).json()["documents"]
    print("search tag:Drill ->", [item["title"] for item in found])
    ok &= detail["title"] == "Drill lease" and any(tag["name"] == "Drill tag" for tag in detail["tags"]) and len(found) == 1
    print("RESTORE VERIFIED" if ok else "RESTORE FAILED")
    sys.exit(0 if ok else 1)
