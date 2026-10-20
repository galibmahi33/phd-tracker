"""Assemble the static dashboard (docs/ + current data) into _site/ for GitHub Pages."""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "_site"))
    args = ap.parse_args()

    out, data_dir = Path(args.out), Path(args.data_dir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "docs", out)
    (out / "data").mkdir(exist_ok=True)

    def read(name, default):
        try:
            return json.loads((data_dir / name).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    payload = {"runs": read("runs.json", [])[-30:], "opportunities": read("opportunities.json", [])}
    (out / "data" / "tracker.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"site built in {out} with {len(payload['opportunities'])} opportunities")


if __name__ == "__main__":
    main()
