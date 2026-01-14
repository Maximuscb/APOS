#!/usr/bin/env python3
"""
bundle_repo_md.py

Run from project root. Generates a SINGLE Markdown file that:
- Honors .gitignore (incl. !negation)
- Skips ignored paths + common junk dirs
- Emits each file in its "native language" via Markdown fenced code blocks
  (```python, ```ts, ```html, etc.)
- Separates files with readable text headers (file path, size)

Output is NOT “flattened into prose”; it’s structured Markdown with code fences.

Usage:
  python bundle_repo_md.py
  python bundle_repo_md.py --out repo_bundle.md
  python bundle_repo_md.py --max-file-bytes 500000
  python bundle_repo_md.py --include-binary   (embeds base64 blocks; default skips binaries)

Requires:
  pip install pathspec
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
from typing import Optional

try:
    import pathspec  # type: ignore
except ImportError as e:
    raise SystemExit("Missing dependency 'pathspec'. Install with: pip install pathspec") from e


DEFAULT_ALWAYS_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode",
    "node_modules", "dist", "build", ".next", ".cache",
    "venv", ".venv", "env",
}
DEFAULT_ALWAYS_EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


EXT_TO_LANG = {
    # common code
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".sh": "bash",
    ".zsh": "zsh",
    ".ps1": "powershell",

    # web / config
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".xml": "xml",
    ".md": "markdown",
    ".sql": "sql",
    ".dockerfile": "dockerfile",
}

FILENAME_TO_LANG = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}


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


def build_spec(root: Path) -> pathspec.PathSpec:
    patterns = read_gitignore_lines(root / ".gitignore")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return True


def detect_lang(path: Path) -> str:
    name = path.name.lower()
    if name in FILENAME_TO_LANG:
        return FILENAME_TO_LANG[name]
    ext = path.suffix.lower()
    return EXT_TO_LANG.get(ext, "")  # empty means "no language tag"


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_ALWAYS_EXCLUDE_DIRS]
        for fn in filenames:
            if fn in DEFAULT_ALWAYS_EXCLUDE_FILES:
                continue
            yield Path(dirpath) / fn


def write_bundle(
    root: Path,
    out_path: Path,
    include_binary: bool,
    max_file_bytes: Optional[int],
) -> tuple[int, int]:
    spec = build_spec(root)

    included = 0
    skipped = 0

    # clear existing file
    out_path.write_text("", encoding="utf-8")

    with out_path.open("a", encoding="utf-8", newline="\n") as out:
        out.write("# Repository Bundle\n\n")
        out.write(f"- Root: `{root.as_posix()}`\n")
        out.write(f"- Generated: `bundle_repo_md.py`\n\n")
        out.write("---\n\n")

        for abs_path in iter_files(root):
            try:
                rel = abs_path.relative_to(root)
            except ValueError:
                skipped += 1
                continue

            rel_posix = rel.as_posix()

            # do not include the bundle itself
            if abs_path.resolve() == out_path.resolve():
                skipped += 1
                continue

            # .gitignore match uses posix paths
            if spec.match_file(rel_posix):
                skipped += 1
                continue

            try:
                size = abs_path.stat().st_size
            except Exception:
                skipped += 1
                continue

            if max_file_bytes is not None and size > max_file_bytes:
                skipped += 1
                continue

            binary = is_binary(abs_path)
            if binary and not include_binary:
                skipped += 1
                continue

            lang = detect_lang(abs_path)

            out.write(f"## `{rel_posix}`\n\n")
            out.write(f"- Bytes: `{size}`\n")
            if binary:
                out.write("- Type: `binary (base64)`\n")
            else:
                out.write("- Type: `text`\n")
            out.write("\n")

            fence = "```"  # standard markdown fence
            out.write(f"{fence}{lang}\n")

            try:
                if binary:
                    b64 = base64.b64encode(abs_path.read_bytes()).decode("ascii")
                    out.write(b64)
                    out.write("\n")
                else:
                    text = abs_path.read_text(encoding="utf-8", errors="replace")
                    out.write(text)
                    if not text.endswith("\n"):
                        out.write("\n")
            except Exception:
                # write a placeholder and continue
                out.write("[[UNREADABLE FILE]]\n")

            out.write(f"{fence}\n\n---\n\n")
            included += 1

    return included, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bundle repo into a single Markdown file with per-file fenced code blocks, honoring .gitignore."
    )
    parser.add_argument("--root", default=".", help="Project root (default: .)")
    parser.add_argument("--out", default="repo_bundle.md", help="Output bundle file (default: repo_bundle.md)")
    parser.add_argument("--include-binary", action="store_true", help="Embed binary files as base64 blocks (default: skip)")
    parser.add_argument("--max-file-bytes", type=int, default=None, help="Skip files larger than this many bytes")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    included, skipped = write_bundle(
        root=root,
        out_path=out_path,
        include_binary=args.include_binary,
        max_file_bytes=args.max_file_bytes,
    )

    print(f"Wrote: {out_path}")
    print(f"Included files: {included}")
    print(f"Skipped files:  {skipped}")


if __name__ == "__main__":
    main()
