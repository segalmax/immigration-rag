"""
scripts/upload_uscis.py
Bulk upload the local USCIS clean corpus to S3.
S3 key is derived from the file's H1/H2 headers: uscis_policy_manual_clean/{h1_slug}/{h2_slug}/{filename}

Usage:
    python scripts/upload_uscis.py
    python scripts/upload_uscis.py --dry-run
    python scripts/upload_uscis.py --limit 5
"""
import argparse
import os
import pathlib
import re

import boto3
import dotenv

dotenv.load_dotenv()

CLEAN_ROOT   = pathlib.Path(__file__).parent.parent / "data" / "uscis_policy_manual_clean"
S3_BUCKET    = os.environ["S3_BUCKET"]
REGION       = os.environ["AWS_REGION"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bulk upload USCIS clean corpus to S3")
    p.add_argument("--dry-run", action="store_true", help="Print what would happen, no uploads")
    p.add_argument("--limit", type=int, default=0, help="Max files to process (0 = all)")
    return p.parse_args()


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def extract_top_headers(text: str) -> tuple:
    h1 = h2 = h3 = ""
    for line in text.splitlines():
        if line.startswith("# ")   and not h1: h1 = line[2:].strip()
        elif line.startswith("## ") and not h2: h2 = line[3:].strip()
        elif line.startswith("### ") and not h3: h3 = line[4:].strip()
        if h1 and h2 and h3:
            break
    return h1, h2, h3


def s3_key_for(h1: str, h2: str, filename: str) -> str:
    if h1 and h2:
        return f"uscis_policy_manual_clean/{slugify(h1)}/{slugify(h2)}/{filename}"
    return f"uscis_policy_manual_clean/{filename}"


def upload_file(s3, md_path: pathlib.Path, dry_run: bool) -> str:
    text     = md_path.read_text(encoding="utf-8")
    h1, h2, h3 = extract_top_headers(text)
    key      = s3_key_for(h1, h2, md_path.name)
    if dry_run:
        print(f"  [dry-run] would upload → {key}")
        return key
    s3.put_object(
        Bucket      = S3_BUCKET,
        Key         = key,
        Body        = text.encode("utf-8"),
        ContentType = "text/markdown",
        Metadata    = {"category": "uscis"},
    )
    return key


def run(args: argparse.Namespace) -> None:
    s3 = boto3.client("s3", region_name=REGION)

    files = sorted(CLEAN_ROOT.rglob("*.md"))
    if args.limit:
        files = files[:args.limit]

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Uploading {len(files)} files to s3://{S3_BUCKET}/uscis_policy_manual_clean/")
    for i, md_path in enumerate(files, 1):
        key = upload_file(s3, md_path, args.dry_run)
        print(f"  [{i}/{len(files)}] {key}")

    print(f"\nDone. {'Would have uploaded' if args.dry_run else 'Uploaded'} {len(files)} files.")


if __name__ == "__main__":
    run(parse_args())
