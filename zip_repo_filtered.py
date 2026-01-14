#!/usr/bin/env python3
"""
zip_repo_filtered.py

Run from project root. Creates a ZIP containing all files that are NOT ignored by .gitignore
(and also skips common junk dirs like .git, node_modules, venv, etc.).

Usage:
  pip install pathspec
  python zip_repo_filtered.py
  python zip_repo_filtered.py --out repo_filtered.zip
  python zip_repo_filtered.py --root .
  python zip_repo_filtered.py --include-dot-gitignore  (include .gitignore itself; default yes)
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path
from typing import Iterable

try:
    import pathspec  # type: ignore
except ImportError as e:
    raise SystemExit("Missing dependency 'pathspec'. Install with: pip install pathspec") from e


DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode",
    "node_modules", "dist", "build", ".next", ".cache",
    "venv", ".venv", "env",
}

DEFAULT_EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def read_gitignore_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def build_gitignore_spec(root: Path) -> pathspec.PathSpec:
    patterns = read_gitignore_lines(root / ".gitignore")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded dirs so we don't descend into them
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS]
        for fn in filenames:
            if fn in DEFAULT_EXCLUDE_FILES:
                continue
            yield Path(dirpath) / fn


def should_include(rel_posix: str, spec: pathspec.PathSpec) -> bool:
    # If .gitignore matches, exclude. Negation patterns (!foo) are handled by pathspec.
    return not spec.match_file(rel_posix)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a zip of the repo excluding anything matched by .gitignore."
    )
    parser.add_argument("--root", default=".", help="Project root (default: .)")
    parser.add_argument("--out", default="repo_filtered.zip", help="Output zip filename (default: repo_filtered.zip)")
    parser.add_argument(
        "--include-dot-gitignore",
        action="store_true",
        default=True,
        help="Include the .gitignore file itself (default: True).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    # Avoid accidentally zipping an existing output zip inside the root
    if out_path.exists():
        out_path.unlink()

    spec = build_gitignore_spec(root)

    included = 0
    skipped = 0

    # Create zip
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path in iter_files(root):
            rel = abs_path.relative_to(root)
            rel_posix = rel.as_posix()

            # Don't include the output zip itself if root/out overlap
            if abs_path.resolve() == out_path.resolve():
                skipped += 1
                continue

            if rel_posix == ".gitignore":
                if args.include_dot_gitignore:
                    zf.write(abs_path, arcname=rel_posix)
                    included += 1
                else:
                    skipped += 1
                continue

            if should_include(rel_posix, spec):
                # Ensure symlinks are handled safely: store the linked file contents by default
                # (skip if it's a broken link)
                try:
                    if abs_path.is_symlink():
                        target = abs_path.resolve(strict=True)
                        # write the *target file* contents under the symlink path name
                        zf.write(target, arcname=rel_posix)
                    else:
                        zf.write(abs_path, arcname=rel_posix)
                    included += 1
                except Exception:
                    skipped += 1
            else:
                skipped += 1

    print(f"Wrote: {out_path}")
    print(f"Included files: {included}")
    print(f"Skipped files:  {skipped}")
    print("Upload the .zip file here.")


if __name__ == "__main__":
    main()
