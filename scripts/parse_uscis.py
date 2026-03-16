"""
Parse the USCIS Policy Manual HTML export into a hierarchical folder of .md files.

Structure mirrors the document:
  uscis_policy_manual/
    volume_01_general_policies_and_procedures/
      part_a_public_services/
        chapter_01_purpose_and_background.md
        ...

Usage:
  python parse_uscis.py [--input uscis_policy_manual.html] [--output uscis_policy_manual]
"""

import argparse
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md


BASE_URL = "https://www.uscis.gov"


def slugify(text: str) -> str:
    """Convert heading text to a filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text).strip("_")
    return text


def pad_number(text: str) -> str:
    """Zero-pad leading numbers in slugs: volume_1 → volume_01, chapter_5 → chapter_05."""
    return re.sub(r"(\b)(\d{1,2})(\b)", lambda m: m.group(1) + m.group(2).zfill(2) + m.group(3), text)


def make_slug(title: str) -> str:
    return pad_number(slugify(title))


def extract_source_url(chapter_article) -> str:
    """Extract the canonical URL from the nested book node article."""
    inner = chapter_article.find("article", class_="node")
    if inner:
        link = inner.find("h2")
        if link:
            a = link.find("a", href=True)
            if a and a["href"]:
                href = a["href"]
                if href.startswith("/"):
                    return BASE_URL + href
                return href
    return ""


def extract_body_html(chapter_article) -> str:
    """Extract the main body HTML from a chapter article."""
    body_div = chapter_article.find("div", class_="field--name-body")
    if body_div:
        # Get the inner formatted div
        inner = body_div.find("div", class_="text-formatted")
        if inner:
            return str(inner)
        return str(body_div)
    return ""


def html_to_markdown(html: str) -> str:
    """Convert HTML body to clean Markdown."""
    result = md(
        html,
        heading_style="ATX",
        bullets="-",
        strip=["a"],  # strip hyperlinks but keep link text
    )
    # Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def write_chapter(path: Path, volume_title: str, part_title: str, chapter_title: str, source_url: str, body_md: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {volume_title}\n")
        f.write(f"## {part_title}\n")
        f.write(f"### {chapter_title}\n\n")
        if source_url:
            f.write(f"> Source: {source_url}\n\n")
        f.write("---\n\n")
        f.write(body_md)
        f.write("\n")


def parse(input_path: Path, output_dir: Path):
    print(f"Reading {input_path} ({input_path.stat().st_size / 1_000_000:.1f} MB)...")
    with open(input_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")

    volumes = soup.find_all("article", class_=lambda c: c and "book-node-depth-2" in c.split())
    print(f"Found {len(volumes)} depth-2 nodes (volumes + misc)")

    chapters_written = 0

    for vol_article in volumes:
        vol_h1 = vol_article.find("h1", class_="book-node-heading-depth-2")
        if not vol_h1:
            continue
        vol_title = vol_h1.get_text(strip=True)

        # Only process actual Volume nodes
        if not vol_title.lower().startswith("volume"):
            continue

        vol_slug = make_slug(vol_title)
        vol_dir = output_dir / vol_slug
        print(f"\n  {vol_title}")

        parts = vol_article.find_all("article", class_=lambda c: c and "book-node-depth-3" in c.split())

        for part_article in parts:
            part_h1 = part_article.find("h1", class_="book-node-heading-depth-3")
            if not part_h1:
                continue
            part_title = part_h1.get_text(strip=True)
            part_slug = make_slug(part_title)
            part_dir = vol_dir / part_slug
            print(f"    {part_title}")

            chapters = part_article.find_all("article", class_=lambda c: c and "book-node-depth-4" in c.split())

            for chap_article in chapters:
                chap_h1 = chap_article.find("h1", class_="book-node-heading-depth-4")
                if not chap_h1:
                    continue
                chap_title = chap_h1.get_text(strip=True)
                chap_slug = make_slug(chap_title)
                source_url = extract_source_url(chap_article)
                body_html = extract_body_html(chap_article)
                body_md = html_to_markdown(body_html) if body_html else "_No content._"

                out_path = part_dir / f"{chap_slug}.md"
                write_chapter(out_path, vol_title, part_title, chap_title, source_url, body_md)
                chapters_written += 1
                print(f"      -> {out_path.relative_to(output_dir)}")

    print(f"\nDone. Wrote {chapters_written} chapter files to {output_dir}/")


_BASE = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser(description="Parse USCIS Policy Manual HTML into structured .md files")
    parser.add_argument("--input", default=str(_BASE / "data/raw/uscis_policy_manual.html"), help="Path to downloaded HTML file")
    parser.add_argument("--output", default=str(_BASE / "data/uscis_policy_manual"), help="Output directory")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: {input_path} not found. Download it first with:")
        print(f"  curl -L -o {input_path} https://www.uscis.gov/book/export/html/68600")
        sys.exit(1)

    parse(input_path, output_dir)


if __name__ == "__main__":
    main()
