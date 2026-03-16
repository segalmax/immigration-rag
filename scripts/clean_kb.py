"""
Clean the USCIS Policy Manual knowledge base.

Reads uscis_policy_manual/ → writes uscis_policy_manual_clean/
Never modifies the source.

Cleaning rules:
  1. Exclude reserved stubs (body is only _No content._)
  2. Strip inline footnote refs **[n]**
  3. Strip ## Footnotes section and everything after it
  4. Collapse excessive blank lines

Usage:
  python clean_kb.py [--input uscis_policy_manual] [--output uscis_policy_manual_clean] [--log clean_kb.log]
"""

import argparse
import re
from pathlib import Path


FOOTNOTE_REF_RE = re.compile(
    r'\*\*\[[\d*]+\]{1,2}\*\*'   # **[n]**, **[1****0****]**, **[8]]** (multi-digit or double-bracket)
    r'|\[\d+\](?=\s*\||\s*$)'    # bare [n] at end of line or before table cell separator
)
BLANK_LINES_RE = re.compile(r'\n{3,}')


def is_reserved(text: str) -> bool:
    parts = text.split("---\n", maxsplit=1)
    if len(parts) < 2:
        return False
    return parts[1].strip() == "_No content._"


def strip_footnote_refs(text: str) -> tuple[str, int]:
    """Remove **[n]** patterns. Returns (cleaned_text, count_removed)."""
    matches = FOOTNOTE_REF_RE.findall(text)
    return FOOTNOTE_REF_RE.sub("", text), len(matches)


def strip_footnotes_section(text: str) -> tuple[str, bool]:
    """Remove ## Footnotes (and ## Footnote) section and everything after it."""
    for marker in ("\n## Footnotes\n", "\n## Footnote\n"):
        idx = text.find(marker)
        if idx != -1:
            return text[:idx].rstrip() + "\n", True
    return text, False


def clean_whitespace(text: str) -> str:
    return BLANK_LINES_RE.sub("\n\n", text)


def clean_file(text: str) -> tuple[str | None, str]:
    """
    Returns (cleaned_text, log_action).
    Returns (None, log_action) if file should be excluded.
    """
    if is_reserved(text):
        return None, "EXCLUDED"

    original = text
    refs_stripped = 0
    footnotes_stripped = False

    text, refs_stripped = strip_footnote_refs(text)
    text, footnotes_stripped = strip_footnotes_section(text)
    text = clean_whitespace(text)

    if refs_stripped > 0 or footnotes_stripped:
        action = f"CLEANED   refs={refs_stripped} footnotes={'yes' if footnotes_stripped else 'no'}"
    else:
        action = "COPIED    refs=0 footnotes=no"

    return text, action


_BASE = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(_BASE / "data/uscis_policy_manual"))
    parser.add_argument("--output", default=str(_BASE / "data/uscis_policy_manual_clean"))
    parser.add_argument("--log", default=str(_BASE / "logs/clean_kb.log"))
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    log_path = Path(args.log)

    if not input_dir.exists():
        print(f"Error: {input_dir} not found.")
        return

    files = sorted(input_dir.rglob("*.md"))
    total = len(files)
    excluded = 0
    cleaned = 0
    copied = 0

    log_lines = []

    for f in files:
        rel = f.relative_to(input_dir)
        text = f.read_text(encoding="utf-8")
        result, action = clean_file(text)

        log_lines.append(f"{action:<10}  {rel}")

        if result is None:
            excluded += 1
            continue

        out_path = output_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")

        if action.startswith("CLEANED"):
            cleaned += 1
        else:
            copied += 1

    summary = f"SUMMARY: total={total} excluded={excluded} cleaned={cleaned} copied={copied}"
    log_lines.append("")
    log_lines.append(summary)

    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print(f"Done.")
    print(f"  {summary}")
    print(f"  Output: {output_dir}/")
    print(f"  Log:    {log_path}")


if __name__ == "__main__":
    main()
