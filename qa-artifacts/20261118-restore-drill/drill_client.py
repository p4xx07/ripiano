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

def mcp(token):
    """HTTP status of an MCP initialize call with this agent token (200 = accepted, 401 = refused)."""
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "restore-drill", "version": "1"}}}
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"}).status_code


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
    # Paper copy in a nested location, and two agents: one active, one revoked.
    shelf = client.post("/api/locations", json={"name": "Drill shelf"}, headers=headers()).json()
    box = client.post("/api/locations", json={"name": "Drill box", "parent_id": shelf["id"]}, headers=headers()).json()
    copy = client.post(f"/api/documents/{first}/copies", json={"location_id": box["id"]}, headers=headers())
    assert copy.status_code == 201, copy.text
    data["sticker"] = copy.json()["sticker_code"]
    data["location_path"] = copy.json()["location_path"]
    agents = {}
    for name in ("Drill active agent", "Drill revoked agent"):
        response = client.post("/api/agents", json={"name": name, "scopes": ["documents:search"], "expires_in_days": 30, "password": data["password"]}, headers=headers())
        assert response.status_code == 201, response.text
        agents[name] = response.json()
    assert client.delete(f"/api/agents/{agents['Drill revoked agent']['id']}", headers=headers()).status_code == 200
    data["tokens"] = {name: item["token"] for name, item in agents.items()}
    print("before backup: mcp active", mcp(data["tokens"]["Drill active agent"]), "revoked", mcp(data["tokens"]["Drill revoked agent"]))
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
    sticker = client.get(f"/api/stickers/{data['sticker']}")
    found_path = json.dumps(sticker.json(), ensure_ascii=False)
    path_ok = sticker.status_code == 200 and all(json.dumps(part, ensure_ascii=False) in found_path for part in data["location_path"])
    print("sticker", data["sticker"], sticker.status_code, "location kept" if path_ok else "LOCATION LOST", data["location_path"])
    grants = {item["name"]: item for item in client.get("/api/agents").json()["grants"]}
    revoked_kept = grants["Drill revoked agent"]["revoked_at"] is not None and grants["Drill active agent"]["revoked_at"] is None
    active, revoked = mcp(data["tokens"]["Drill active agent"]), mcp(data["tokens"]["Drill revoked agent"])
    print("grants revoked state kept" if revoked_kept else "GRANT STATE LOST", "| mcp active", active, "revoked", revoked)
    ok &= path_ok and revoked_kept and active == 200 and revoked == 401
    print("RESTORE VERIFIED" if ok else "RESTORE FAILED")
    sys.exit(0 if ok else 1)
