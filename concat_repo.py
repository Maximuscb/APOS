#!/usr/bin/env python3
"""
concat_repo.py

Run from project root. Creates ONE output file that concatenates all non-ignored
files, respecting .gitignore rules — EXCEPT it will ALWAYS include the APOS DB
(even if ignored), embedding it as base64 so it can live inside a text bundle.

Usage:
  python concat_repo.py --out repo_bundle.txt

Notes:
  - Requires: pip install pathspec
  - Honors .gitignore patterns (incl. negation !pattern).
  - Skips common VCS + OS junk by default (.git, etc.).
  - Skips binary files by default, EXCEPT the APOS DB which is always embedded as base64.
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
from typing import Iterable, Optional

try:
    import pathspec  # type: ignore
except ImportError as e:
    raise SystemExit(
        "Missing dependency 'pathspec'. Install it with:\n"
        "  pip install pathspec\n"
    ) from e


DEFAULT_ALWAYS_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".cache",
    "venv",
    ".venv",
    "env",
}

DEFAULT_ALWAYS_EXCLUDE_FILES = {
    ".DS_Store",
    "Thumbs.db",
}


def read_gitignore_lines(gitignore_path: Path) -> list[str]:
    if not gitignore_path.exists():
        return []
    lines: list[str] = []
    for raw in gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


def build_gitignore_spec(root: Path) -> pathspec.PathSpec:
    patterns = read_gitignore_lines(root / ".gitignore")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return True


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_ALWAYS_EXCLUDE_DIRS]
        for fn in filenames:
            if fn in DEFAULT_ALWAYS_EXCLUDE_FILES:
                continue
            yield Path(dirpath) / fn


def should_exclude(rel_posix: str, spec: pathspec.PathSpec) -> bool:
    return spec.match_file(rel_posix)


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def embed_file_as_base64(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"[BINARY FILE BASE64]\n{b64}\n"


def normalize_apos_db_paths(root: Path, db_paths: list[str]) -> set[Path]:
    """
    Convert user-provided db paths to absolute Paths under root when possible.
    Accepts relative paths like "instance/pos.sqlite3" or "pos.sqlite3".
    """
    out: set[Path] = set()
    for p in db_paths:
        candidate = Path(p)
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        out.add(candidate)
    return out


def discover_default_apos_db_candidates(root: Path) -> set[Path]:
    """
    Best-effort discovery for typical APOS DB filenames/locations.
    Included even if ignored by .gitignore.

    Common patterns:
      - instance/pos.sqlite3
      - instance/apos.sqlite3
      - any *.sqlite3 directly under instance/
      - pos.sqlite3 at root (less common)
    """
    candidates: set[Path] = set()

    instance_dir = root / "instance"
    if instance_dir.exists() and instance_dir.is_dir():
        for name in ("pos.sqlite3", "apos.sqlite3", "pos.db", "apos.db"):
            p = (instance_dir / name).resolve()
            if p.exists() and p.is_file():
                candidates.add(p)
        # Any sqlite3 files in instance/
        for p in instance_dir.glob("*.sqlite3"):
            if p.is_file():
                candidates.add(p.resolve())

    for name in ("pos.sqlite3", "apos.sqlite3", "pos.db", "apos.db"):
        p = (root / name).resolve()
        if p.exists() and p.is_file():
            candidates.add(p)

    return candidates


def write_bundle(
    root: Path,
    out_path: Path,
    apos_db_abs_paths: set[Path],
    include_binary: bool = False,
    max_file_bytes: Optional[int] = None,
) -> tuple[int, int]:
    """
    Returns (files_included, files_skipped).
    """
    spec = build_gitignore_spec(root)

    included = 0
    skipped = 0

    out_path.write_text("", encoding="utf-8")

    def write_header(out, rel_posix: str, size: int, forced: bool = False) -> None:
        out.write("\n")
        out.write("=" * 100 + "\n")
        out.write(f"FILE: {rel_posix}\n")
        out.write(f"BYTES: {size}\n")
        if forced:
            out.write("NOTE: INCLUDED REGARDLESS OF .gitignore (APOS DB FORCE-INCLUDE)\n")
        out.write("=" * 100 + "\n")

    with out_path.open("a", encoding="utf-8", newline="\n") as out:
        for abs_path in iter_files(root):
            abs_resolved = abs_path.resolve()

            # Never include the output file itself
            if abs_resolved == out_path.resolve():
                skipped += 1
                continue

            # Rel path (for printing + ignore matching)
            try:
                rel = abs_resolved.relative_to(root)
            except ValueError:
                skipped += 1
                continue
            rel_posix = rel.as_posix()

            # Stat
            try:
                size = abs_resolved.stat().st_size
            except Exception:
                skipped += 1
                continue

            if max_file_bytes is not None and size > max_file_bytes:
                skipped += 1
                continue

            # FORCE INCLUDE APOS DB, regardless of gitignore and binary skipping
            if abs_resolved in apos_db_abs_paths:
                try:
                    content = embed_file_as_base64(abs_resolved)
                except Exception:
                    skipped += 1
                    continue
                write_header(out, rel_posix, size, forced=True)
                out.write(content)
                included += 1
                continue

            # Normal .gitignore behavior
            if should_exclude(rel_posix, spec):
                skipped += 1
                continue

            # Binary handling (default skip)
            if not include_binary and is_binary_file(abs_resolved):
                skipped += 1
                continue

            # Read content
            try:
                if include_binary and is_binary_file(abs_resolved):
                    content = embed_file_as_base64(abs_resolved)
                else:
                    content = safe_read_text(abs_resolved)
            except Exception:
                skipped += 1
                continue

            write_header(out, rel_posix, size, forced=False)
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")

            included += 1

    return included, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Concatenate repo files, honoring .gitignore, but force-include APOS DB.")
    parser.add_argument("--root", default=".", help="Project root (default: .)")
    parser.add_argument("--out", default="repo_bundle.txt", help="Output file path (default: repo_bundle.txt)")
    parser.add_argument(
        "--include-binary",
        action="store_true",
        help="Include other binary files as base64 blocks (default: skip binaries; APOS DB is always included).",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=None,
        help="Skip files larger than this many bytes (default: no limit).",
    )
    parser.add_argument(
        "--apos-db",
        action="append",
        default=[],
        help=(
            "Path to APOS DB file to force-include (can be repeated). "
            "If omitted, script will try common defaults like instance/pos.sqlite3."
        ),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    # Determine which DB file(s) to force include
    user_db_paths = normalize_apos_db_paths(root, args.apos_db) if args.apos_db else set()
    discovered = discover_default_apos_db_candidates(root) if not user_db_paths else set()
    apos_db_abs_paths = user_db_paths | discovered

    included, skipped = write_bundle(
        root=root,
        out_path=out_path,
        apos_db_abs_paths=apos_db_abs_paths,
        include_binary=args.include_binary,
        max_file_bytes=args.max_file_bytes,
    )

    print(f"Wrote: {out_path}")
    print(f"Included files: {included}")
    print(f"Skipped files:  {skipped}")

    if apos_db_abs_paths:
        existing = [p for p in apos_db_abs_paths if p.exists()]
        missing = [p for p in apos_db_abs_paths if not p.exists()]
        if existing:
            print("APOS DB force-included:")
            for p in existing:
                try:
                    rel = p.relative_to(root).as_posix()
                except ValueError:
                    rel = str(p)
                print(f"  - {rel}")
        if missing:
            print("APOS DB paths requested but not found:")
            for p in missing:
                print(f"  - {p}")

    print("Tip: upload the output file to ChatGPT for review.")


if __name__ == "__main__":
    main()
