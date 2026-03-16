"""
Analyze the USCIS Policy Manual knowledge base and write kb_report.md.

Usage:
  python analyze_kb.py [--input uscis_policy_manual] [--output kb_report.md]
"""

import argparse
import re
import statistics
from collections import defaultdict
from pathlib import Path


def is_reserved(text: str) -> bool:
    """True if the file body is only the _No content._ placeholder."""
    # Body starts after the '---' separator line
    parts = text.split("---\n", maxsplit=1)
    if len(parts) < 2:
        return False
    body = parts[1].strip()
    return body == "_No content._"


def count_footnote_refs(text: str) -> int:
    return len(re.findall(r'\*\*\[\d+\]\*\*', text))


def count_sections(text: str) -> int:
    """Count top-level ## sections (excluding the breadcrumb ## Part line)."""
    lines = text.splitlines()
    return sum(1 for l in lines if l.startswith("## ") and not l.startswith("## Part "))


def table_stats(text: str):
    """Return (has_table, single_col_count, multi_col_count, flat_list_rows)."""
    lines = text.splitlines()
    single_col = 0
    multi_col = 0
    flat_list_rows = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and "| ---" in lines[i + 1]:
            sep = lines[i + 1]
            cols = sep.count("---")
            if cols == 1:
                single_col += 1
            else:
                multi_col += 1
        if line.startswith("|") and "- " in line and "| ---" not in line:
            flat_list_rows += 1
        i += 1
    has_table = (single_col + multi_col) > 0
    return has_table, single_col, multi_col, flat_list_rows


def word_count(text: str) -> int:
    return len(text.split())


def bucket(w: int) -> str:
    if w < 100:
        return "< 100"
    elif w < 500:
        return "100–499"
    elif w < 2000:
        return "500–1,999"
    elif w < 5000:
        return "2,000–4,999"
    elif w < 8000:
        return "5,000–7,999"
    else:
        return "8,000+"


BUCKET_ORDER = ["< 100", "100–499", "500–1,999", "2,000–4,999", "5,000–7,999", "8,000+"]


def analyze(corpus_dir: Path):
    files = sorted(corpus_dir.rglob("*.md"))

    total = len(files)
    reserved_files = []
    clean_files = []

    vol_stats = defaultdict(lambda: {"files": 0, "stubs": 0, "words": []})
    all_words = []
    buckets = defaultdict(int)

    oversized = []  # (words, section_count, path)
    footnote_data = []  # (count, path)
    total_footnote_refs = 0

    table_files = 0
    total_single_col = 0
    total_multi_col = 0
    total_flat_list_rows = 0
    table_file_count = 0

    for f in files:
        text = f.read_text(encoding="utf-8")
        parts = f.relative_to(corpus_dir).parts
        vol = parts[0] if parts else "unknown"

        reserved = is_reserved(text)
        wc = word_count(text)
        refs = count_footnote_refs(text)
        sections = count_sections(text)
        has_tbl, sc, mc, flr = table_stats(text)

        vol_stats[vol]["files"] += 1
        vol_stats[vol]["words"].append(wc)

        if reserved:
            reserved_files.append(f.relative_to(corpus_dir))
            vol_stats[vol]["stubs"] += 1
        else:
            clean_files.append(f.relative_to(corpus_dir))
            all_words.append(wc)
            buckets[bucket(wc)] += 1

        if refs > 0:
            footnote_data.append((refs, f.relative_to(corpus_dir)))
            total_footnote_refs += refs

        if has_tbl:
            table_file_count += 1
            total_single_col += sc
            total_multi_col += mc
            total_flat_list_rows += flr

        if not reserved and wc >= 8000:
            oversized.append((wc, sections, f.relative_to(corpus_dir)))

    footnote_data.sort(reverse=True)
    oversized.sort(reverse=True)

    return {
        "total": total,
        "reserved": reserved_files,
        "clean_count": len(clean_files),
        "all_words": all_words,
        "buckets": buckets,
        "oversized": oversized,
        "footnote_data": footnote_data,
        "total_footnote_refs": total_footnote_refs,
        "table_file_count": table_file_count,
        "total_single_col": total_single_col,
        "total_multi_col": total_multi_col,
        "total_flat_list_rows": total_flat_list_rows,
        "vol_stats": vol_stats,
    }


def render_report(data: dict, corpus_dir: Path) -> str:
    lines = []
    w = lines.append

    w("# USCIS Policy Manual — Knowledge Base Quality Report\n")
    w(f"**Corpus:** `{corpus_dir}/`\n")

    # 1. Summary
    w("---\n")
    w("## 1. Summary\n")
    words = data["all_words"]
    w("| Metric | Value |")
    w("|--------|-------|")
    w(f"| Total files | {data['total']} |")
    w(f"| Reserved stubs (excluded) | {len(data['reserved'])} |")
    w(f"| Clean files | {data['clean_count']} |")
    w(f"| Total words (clean files) | {sum(words):,} |")
    w(f"| Mean words/file | {statistics.mean(words):,.0f} |")
    w(f"| Median words/file | {statistics.median(words):,.0f} |")
    w(f"| Min words/file | {min(words):,} |")
    w(f"| Max words/file | {max(words):,} |")
    w("")

    # 2. Word count distribution
    w("---\n")
    w("## 2. Word Count Distribution (clean files only)\n")
    w("| Range | Files | Bar |")
    w("|-------|-------|-----|")
    for b in BUCKET_ORDER:
        count = data["buckets"].get(b, 0)
        bar = "█" * (count // 3)
        w(f"| {b} | {count} | {bar} |")
    w("")

    # 3. Oversized files
    w("---\n")
    w("## 3. Oversized Files (≥ 8,000 words)\n")
    w("*These exceed typical embedding model context windows. Flag for splitting at `##` section level in the chunking phase.*\n")
    w("| Words | Sections | File |")
    w("|-------|----------|------|")
    for wc, sec, path in data["oversized"]:
        w(f"| {wc:,} | {sec} | `{path}` |")
    w("")

    # 4. Reserved stubs
    w("---\n")
    w("## 4. Reserved Stubs (48 files — excluded from clean corpus)\n")
    w("*These are USCIS placeholder chapters not yet written. Content is only `_No content._`.*\n")
    for path in data["reserved"]:
        w(f"- `{path}`")
    w("")

    # 5. Footnote noise
    w("---\n")
    w("## 5. Footnote Noise\n")
    w(f"- **Total inline `**[n]**` refs across all files:** {data['total_footnote_refs']:,}")
    w(f"- **Files with at least one ref:** {len(data['footnote_data'])}\n")
    w("**Top 10 files by footnote ref count:**\n")
    w("| Refs | File |")
    w("|------|------|")
    for count, path in data["footnote_data"][:10]:
        w(f"| {count} | `{path}` |")
    w("")

    # 6. Table breakdown
    w("---\n")
    w("## 6. Table Breakdown\n")
    w("| Metric | Count |")
    w("|--------|-------|")
    w(f"| Files containing tables | {data['table_file_count']} |")
    w(f"| Single-column tables (eligibility checklists) | {data['total_single_col']} |")
    w(f"| Multi-column tables | {data['total_multi_col']} |")
    w(f"| Table rows with flattened list items (`- a - b - c`) | {data['total_flat_list_rows']} |")
    w("")
    w("*Flattened list rows occur when HTML `<ul><li>` inside `<td>` is converted. Text is preserved but formatting is cramped. Acceptable for now.*\n")

    # 7. Per-volume summary
    w("---\n")
    w("## 7. Per-Volume Summary\n")
    w("| Volume | Files | Stubs | Clean | Total Words | Median Words |")
    w("|--------|-------|-------|-------|-------------|--------------|")
    for vol in sorted(data["vol_stats"]):
        vs = data["vol_stats"][vol]
        clean = vs["files"] - vs["stubs"]
        total_w = sum(vs["words"])
        med_w = statistics.median(vs["words"]) if vs["words"] else 0
        w(f"| `{vol}` | {vs['files']} | {vs['stubs']} | {clean} | {total_w:,} | {med_w:,.0f} |")
    w("")

    return "\n".join(lines)


_BASE = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(_BASE / "data/uscis_policy_manual"))
    parser.add_argument("--output", default=str(_BASE / "reports/kb_report.md"))
    args = parser.parse_args()

    corpus_dir = Path(args.input)
    if not corpus_dir.exists():
        print(f"Error: {corpus_dir} not found.")
        return

    print(f"Analyzing {corpus_dir}...")
    data = analyze(corpus_dir)
    report = render_report(data, corpus_dir)

    Path(args.output).write_text(report, encoding="utf-8")
    print(f"Report written to {args.output}")
    print(f"  {data['total']} total files, {len(data['reserved'])} stubs, {data['clean_count']} clean")
    print(f"  {data['total_footnote_refs']:,} inline footnote refs to strip")
    print(f"  {len(data['oversized'])} oversized files (≥8K words)")


if __name__ == "__main__":
    main()
