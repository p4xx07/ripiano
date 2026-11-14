"""Write a launchd plist for a 10:00 daily run plus login catch-up."""

import plistlib
import shutil
from pathlib import Path


def main():
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("Install uv first and rerun this script")
    project = Path(__file__).resolve().parent
    logs = Path.home() / ".local/share/ripiano-classifier"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = Path.home() / "Library/LaunchAgents/com.ripiano.classifier.plist"
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Label": "com.ripiano.classifier",
        "ProgramArguments": [uv, "run", "--project", str(project), "python", str(project / "classify.py")],
        "StartCalendarInterval": {"Hour": 10, "Minute": 0},
        "RunAtLoad": True,
        "StandardOutPath": str(logs / "classifier.out.log"),
        "StandardErrorPath": str(logs / "classifier.err.log"),
    }
    destination.write_bytes(plistlib.dumps(data))
    print(f"Wrote {destination}")
    print(f"Load with: launchctl bootstrap gui/$(id -u) {destination}")


if __name__ == "__main__":
    main()
