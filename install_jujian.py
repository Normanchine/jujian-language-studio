"""Install the renamed package beside the old one and preserve local study data."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "dist-jujian-stage" / "句间"
OLD = ROOT / "dist" / "每日日语"
ESSAY_BACKUP = ROOT / "dist" / "每日日语-before-feedback-20261014" / "data" / "essays"
NEW = ROOT / "dist" / "句间"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.is_file())


def main() -> None:
    for path in (STAGE, OLD, ESSAY_BACKUP, NEW):
        if not path.resolve().is_relative_to(ROOT):
            raise RuntimeError(f"Unexpected path outside workspace: {path}")
    if not (STAGE / "句间.exe").is_file():
        raise FileNotFoundError("Packaged EXE is missing")
    if NEW.exists():
        raise FileExistsError(f"New destination already exists: {NEW}")

    old_data = OLD / "data"
    old_hashes = {path.relative_to(old_data): digest(path) for path in files(old_data)}
    backup_essays = {path.name: digest(path) for path in ESSAY_BACKUP.glob("*.json")}
    print(f"Before install: current data={len(old_hashes)} files, backup essays={len(backup_essays)}")

    shutil.copytree(STAGE, NEW)
    new_data = NEW / "data"
    new_data.mkdir(exist_ok=True)
    for path in files(old_data):
        destination = new_data / path.relative_to(old_data)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    essays = new_data / "essays"
    essays.mkdir(exist_ok=True)
    restored = 0
    for path in sorted(ESSAY_BACKUP.glob("*.json")):
        destination = essays / path.name
        if not destination.exists():
            shutil.copy2(path, destination)
            restored += 1

    for relative, expected in old_hashes.items():
        if digest(old_data / relative) != expected:
            raise RuntimeError(f"Source data changed during install: {relative}")
        if digest(new_data / relative) != expected:
            raise RuntimeError(f"Copied data does not match: {relative}")
    for name, expected in backup_essays.items():
        if digest(ESSAY_BACKUP / name) != expected or digest(essays / name) != expected:
            raise RuntimeError(f"Restored essay does not match: {name}")

    last_project = new_data / "last-project.txt"
    if last_project.exists():
        saved = last_project.read_text(encoding="utf-8")
        rewritten = saved.replace(str(OLD), str(NEW))
        if rewritten != saved:
            last_project.write_text(rewritten, encoding="utf-8")
        selected = Path(rewritten.strip())
        if not selected.resolve().is_relative_to(new_data / "projects"):
            raise RuntimeError(f"Last project did not migrate into new package: {selected}")
        if not selected.exists():
            raise RuntimeError(f"Last project target missing: {selected}")
    print(f"Installed {NEW / '句间.exe'}")
    print(f"Verified {len(old_hashes)} current files; restored {restored} essays; last project valid")


if __name__ == "__main__":
    main()
