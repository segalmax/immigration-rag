"""
kb_dashboard/app.py
Flask dev dashboard for inspecting the USCIS Policy Manual knowledge base.
Runs locally only — not the production RAG API (that lives in ../app.py).
"""
import json
import os
import re
from pathlib import Path

import boto3
import dotenv
import markdown as md_lib
import pandas as pd
import plotly.express as px
import tiktoken
from flask import Flask, render_template, abort, request, jsonify

dotenv.load_dotenv()

app = Flask(__name__)

RAW_ROOT   = Path(__file__).parent.parent / "data" / "uscis_policy_manual"
CLEAN_ROOT = Path(__file__).parent.parent / "data" / "uscis_policy_manual_clean"

S3_CLEAN_PREFIX  = "uscis_policy_manual_clean/"
S3_UPLOAD_PREFIX = "uploads/"

# tiktoken encoder — loaded once
_enc = tiktoken.get_encoding("cl100k_base")


# ── pure helpers (importable by tests) ─────────────────────────────────────

def word_count(text: str) -> int:
    return len(text.split())

def token_count(text: str) -> int:
    return len(_enc.encode(text))

def footnote_count(text: str) -> int:
    """Count original **[n]** style refs (mostly relevant in raw corpus)."""
    return len(re.findall(r'\*\*\[\d+\]\*\*', text))

def residual_footnote_count(text: str) -> int:
    """Count footnote patterns that clean_kb.py missed."""
    markdown_style = re.findall(r'\[\^ *\d+\]', text)
    bare_style     = re.findall(r'\[\d+\](?=[.,;)\s]|\s*$)', text, re.M)
    return len(markdown_style) + len(bare_style)

def section_count(text: str) -> int:
    return len(re.findall(r'^##\s', text, re.MULTILINE))

def is_stub(text: str) -> bool:
    return "_No content._" in text or len(text.strip()) < 30

def vol_sort_key(slug: str) -> int:
    m = re.search(r'_(\d+)_', slug)
    return int(m.group(1)) if m else 999

def pretty_vol(slug: str) -> str:
    parts = slug.split("_")
    nums  = [i for i, p in enumerate(parts) if p.isdigit()]
    if nums:
        n    = parts[nums[0]]
        rest = " ".join(p.capitalize() for p in parts[nums[0]+1:])
        return f"Vol {n} – {rest}"
    return slug.replace("_", " ").title()

def word_bucket(wc: int) -> str:
    if wc < 100:   return "< 100"
    if wc < 500:   return "100–499"
    if wc < 2000:  return "500–1,999"
    if wc < 5000:  return "2,000–4,999"
    if wc < 8000:  return "5,000–7,999"
    return "8,000+"

def token_bucket(tc: int) -> str:
    if tc < 512:   return "< 512"
    if tc < 1024:  return "512–1K"
    if tc < 2048:  return "1K–2K"
    if tc < 4096:  return "2K–4K"
    return "4K+"

WORD_BUCKETS  = ["< 100","100–499","500–1,999","2,000–4,999","5,000–7,999","8,000+"]
TOKEN_BUCKETS = ["< 512","512–1K","1K–2K","2K–4K","4K+"]


# ── corpus scanner ──────────────────────────────────────────────────────────

def _scan_corpus(root: Path, is_clean: bool) -> dict:
    """Scan a corpus directory and return a full stats dict."""
    rows = []
    for md_path in sorted(root.rglob("*.md")):
        rel   = md_path.relative_to(root)
        parts = rel.parts
        text  = md_path.read_text(encoding="utf-8")
        stub  = is_stub(text)
        wc    = word_count(text)
        tc    = token_count(text)
        fn    = footnote_count(text)
        rfn   = residual_footnote_count(text) if is_clean else 0
        rows.append({
            "path":      str(rel),
            "volume":    parts[0] if len(parts) > 0 else "",
            "part":      parts[1] if len(parts) > 1 else "",
            "chapter":   parts[2] if len(parts) > 2 else parts[-1],
            "words":     wc,
            "tokens":    tc,
            "footnotes": fn,
            "residual_footnotes": rfn,
            "sections":  section_count(text),
            "stub":      stub,
            "text":      text,
        })

    df = pd.DataFrame(rows)
    df["vol_label"]    = df["volume"].apply(pretty_vol)
    df["vol_num"]      = df["volume"].apply(vol_sort_key)
    df["word_bucket"]  = df["words"].apply(word_bucket)
    df["token_bucket"] = df["tokens"].apply(token_bucket)

    clean_df = df[~df["stub"]]

    # summary numbers
    wlist = clean_df["words"].tolist()
    tlist = clean_df["tokens"].tolist()
    summary = {
        "total":              len(df),
        "clean":              len(clean_df),
        "stubs":              int(df["stub"].sum()),
        "total_words":        int(clean_df["words"].sum()),
        "mean_words":         int(clean_df["words"].mean()) if len(clean_df) else 0,
        "median_words":       int(clean_df["words"].median()) if len(clean_df) else 0,
        "max_words":          int(clean_df["words"].max()) if len(clean_df) else 0,
        "total_tokens":       int(clean_df["tokens"].sum()),
        "mean_tokens":        int(clean_df["tokens"].mean()) if len(clean_df) else 0,
        "median_tokens":      int(clean_df["tokens"].median()) if len(clean_df) else 0,
        "max_tokens":         int(clean_df["tokens"].max()) if len(clean_df) else 0,
        "total_footnotes":    int(clean_df["footnotes"].sum()),
        "files_w_footnotes":  int((clean_df["footnotes"] > 0).sum()),
        "residual_footnotes": int(clean_df["residual_footnotes"].sum()),
        "oversized_count":    int((clean_df["words"] >= 8000).sum()),
    }

    # word distribution chart
    wd = (clean_df.groupby("word_bucket", observed=True)
                  .size()
                  .reindex(WORD_BUCKETS, fill_value=0)
                  .reset_index(name="count"))
    wd.columns = ["range", "count"]
    fig_w = px.bar(wd, x="count", y="range", orientation="h",
                   color="count", color_continuous_scale="Blues",
                   labels={"count":"Files","range":"Word Count"},
                   title="Word Count Distribution")
    fig_w.update_layout(height=300, margin=dict(l=5,r=5,t=35,b=5),
                        coloraxis_showscale=False,
                        plot_bgcolor="white", paper_bgcolor="white")
    dist_word_chart = fig_w.to_html(full_html=False, include_plotlyjs="cdn")

    # token distribution chart
    td = (clean_df.groupby("token_bucket", observed=True)
                  .size()
                  .reindex(TOKEN_BUCKETS, fill_value=0)
                  .reset_index(name="count"))
    td.columns = ["range", "count"]
    fig_t = px.bar(td, x="count", y="range", orientation="h",
                   color="count", color_continuous_scale="Purples",
                   labels={"count":"Files","range":"Token Count"},
                   title="Token Count Distribution (cl100k_base)")
    fig_t.update_layout(height=300, margin=dict(l=5,r=5,t=35,b=5),
                        coloraxis_showscale=False,
                        plot_bgcolor="white", paper_bgcolor="white")
    dist_token_chart = fig_t.to_html(full_html=False, include_plotlyjs=False)

    # per-volume summary (sorted numerically)
    vol_agg = (clean_df.groupby(["volume","vol_label","vol_num"], observed=True)
                       .agg(files=("path","count"),
                            total_words=("words","sum"),
                            median_words=("words","median"),
                            total_tokens=("tokens","sum"),
                            median_tokens=("tokens","median"),
                            footnotes=("footnotes","sum"))
                       .reset_index()
                       .sort_values("vol_num"))
    stubs_agg = df[df["stub"]].groupby("volume").size().reset_index(name="stubs")
    vol_df = vol_agg.merge(stubs_agg, on="volume", how="left").fillna({"stubs":0})
    vol_df["stubs"]         = vol_df["stubs"].astype(int)
    vol_df["median_words"]  = vol_df["median_words"].astype(int)
    vol_df["median_tokens"] = vol_df["median_tokens"].astype(int)

    # chapter rows for Tabulator pivot table
    chapter_rows = []
    for _, r in clean_df.iterrows():
        chapter_rows.append({
            "volume":   r["vol_label"],
            "part":     r["part"].replace("_"," ").title(),
            "chapter":  r["chapter"].replace(".md","").replace("_"," ").title(),
            "words":    r["words"],
            "tokens":   r["tokens"],
            "footnotes":r["footnotes"],
            "sections": r["sections"],
            "path":     r["path"],
        })

    # oversized + top footnotes + stubs list
    oversized     = clean_df[clean_df["words"] >= 8000].sort_values("words", ascending=False).to_dict("records")
    top_footnotes = clean_df.nlargest(10, "footnotes").to_dict("records")
    stubs_list    = df[df["stub"]].sort_values("path").to_dict("records")

    # footnote gap (clean corpus only)
    footnote_gap = clean_df[clean_df["residual_footnotes"] > 0].to_dict("records") if is_clean else []

    # browse tree (volumes sorted numerically)
    tree = {}
    for _, row in df.sort_values(["vol_num","part","chapter"]).iterrows():
        v, p = row["volume"], row["part"]
        tree.setdefault(v, {}).setdefault(p, []).append(row.to_dict())

    max_words  = int(vol_df["total_words"].max()) if len(vol_df) else 1
    max_tokens = int(vol_df["total_tokens"].max()) if len(vol_df) else 1

    return dict(
        summary=summary,
        dist_word_chart=dist_word_chart,
        dist_token_chart=dist_token_chart,
        vol_df=vol_df.to_dict("records"),
        max_words=max_words,
        max_tokens=max_tokens,
        oversized=oversized,
        top_footnotes=top_footnotes,
        stubs_list=stubs_list,
        footnote_gap=footnote_gap,
        chapter_rows=chapter_rows,
        tree=tree,
        all_files=df.to_dict("records"),
    )


# ── module-level cache ──────────────────────────────────────────────────────

_cache: dict = {}

def load_corpus() -> dict:
    if not _cache:
        clean = _scan_corpus(CLEAN_ROOT, is_clean=True)
        raw   = _scan_corpus(RAW_ROOT,   is_clean=False)
        _cache["clean"]       = clean
        _cache["raw_summary"] = raw["summary"]
    return _cache


# ── S3 corpus scanner ────────────────────────────────────────────────────────

def _s3_client():
    return boto3.client("s3", region_name=os.environ["AWS_REGION"])


def _scan_s3_corpus() -> dict:
    s3        = _s3_client()
    bucket    = os.environ["S3_BUCKET"]
    paginator = s3.get_paginator("list_objects_v2")
    rows = []
    for prefix in [S3_CLEAN_PREFIX, S3_UPLOAD_PREFIX]:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".md"):
                    continue
                text  = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
                rel   = key[len(prefix):]
                parts = rel.split("/")
                if prefix == S3_CLEAN_PREFIX and len(parts) >= 3:
                    vol, part, chapter, path = parts[0], parts[1], parts[2], rel
                else:
                    vol, part, chapter, path = "uploads", "", parts[-1], key
                rows.append({
                    "path":      path,
                    "volume":    vol,
                    "part":      part,
                    "chapter":   chapter,
                    "words":     word_count(text),
                    "tokens":    token_count(text),
                    "sections":  section_count(text),
                    "footnotes": 0,
                    "stub":      False,
                    "text":      text,
                })

    if not rows:
        empty_summary = dict(total=0, total_words=0, mean_words=0, max_words=0,
                             total_tokens=0, mean_tokens=0, max_tokens=0, oversized_count=0)
        return dict(summary=empty_summary, dist_word_chart="<p class='text-gray-400 p-4'>No files found in S3 at prefix: " + S3_CLEAN_PREFIX + "</p>",
                    dist_token_chart="", vol_df=[], max_words=1, max_tokens=1,
                    oversized=[], chapter_rows=[], tree={}, all_files=[])

    df = pd.DataFrame(rows)
    df["vol_label"]    = df["volume"].apply(pretty_vol)
    df["vol_num"]      = df["volume"].apply(vol_sort_key)
    df["word_bucket"]  = df["words"].apply(word_bucket)
    df["token_bucket"] = df["tokens"].apply(token_bucket)

    summary = {
        "total":           len(df),
        "total_words":     int(df["words"].sum()),
        "mean_words":      int(df["words"].mean()),
        "max_words":       int(df["words"].max()),
        "total_tokens":    int(df["tokens"].sum()),
        "mean_tokens":     int(df["tokens"].mean()),
        "max_tokens":      int(df["tokens"].max()),
        "oversized_count": int((df["words"] >= 8000).sum()),
    }

    wd = (df.groupby("word_bucket", observed=True).size()
            .reindex(WORD_BUCKETS, fill_value=0).reset_index(name="count"))
    wd.columns = ["range", "count"]
    fig_w = px.bar(wd, x="count", y="range", orientation="h", color="count",
                   color_continuous_scale="Blues", labels={"count": "Files", "range": "Word Count"},
                   title="Word Count Distribution")
    fig_w.update_layout(height=300, margin=dict(l=5, r=5, t=35, b=5),
                        coloraxis_showscale=False, plot_bgcolor="white", paper_bgcolor="white")
    dist_word_chart = fig_w.to_html(full_html=False, include_plotlyjs="cdn")

    td = (df.groupby("token_bucket", observed=True).size()
            .reindex(TOKEN_BUCKETS, fill_value=0).reset_index(name="count"))
    td.columns = ["range", "count"]
    fig_t = px.bar(td, x="count", y="range", orientation="h", color="count",
                   color_continuous_scale="Purples", labels={"count": "Files", "range": "Token Count"},
                   title="Token Count Distribution (cl100k_base)")
    fig_t.update_layout(height=300, margin=dict(l=5, r=5, t=35, b=5),
                        coloraxis_showscale=False, plot_bgcolor="white", paper_bgcolor="white")
    dist_token_chart = fig_t.to_html(full_html=False, include_plotlyjs=False)

    vol_agg = (df.groupby(["volume", "vol_label", "vol_num"], observed=True)
                 .agg(files=("path", "count"), total_words=("words", "sum"),
                      median_words=("words", "median"), total_tokens=("tokens", "sum"),
                      median_tokens=("tokens", "median"))
                 .reset_index().sort_values("vol_num"))
    vol_agg["median_words"]  = vol_agg["median_words"].astype(int)
    vol_agg["median_tokens"] = vol_agg["median_tokens"].astype(int)

    chapter_rows = [
        {"volume": r["vol_label"], "part": r["part"].replace("_", " ").title(),
         "chapter": r["chapter"].replace(".md", "").replace("_", " ").title(),
         "words": r["words"], "tokens": r["tokens"], "sections": r["sections"], "path": r["path"]}
        for _, r in df.iterrows()
    ]

    oversized = df[df["words"] >= 8000].sort_values("words", ascending=False).to_dict("records")

    tree = {}
    for _, row in df.sort_values(["vol_num", "part", "chapter"]).iterrows():
        tree.setdefault(row["volume"], {}).setdefault(row["part"], []).append(row.to_dict())

    max_words  = int(vol_agg["total_words"].max()) if len(vol_agg) else 1
    max_tokens = int(vol_agg["total_tokens"].max()) if len(vol_agg) else 1

    return dict(summary=summary, dist_word_chart=dist_word_chart, dist_token_chart=dist_token_chart,
                vol_df=vol_agg.to_dict("records"), max_words=max_words, max_tokens=max_tokens,
                oversized=oversized, chapter_rows=chapter_rows, tree=tree, all_files=df.to_dict("records"))


_s3_cache: dict = {}

def load_s3_corpus() -> dict:
    if not _s3_cache:
        _s3_cache.update(_scan_s3_corpus())
    return _s3_cache


# ── routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    d = load_corpus()
    c = d["clean"]
    return render_template(
        "index.html",
        summary=c["summary"],
        summary_raw=d["raw_summary"],
        dist_word_chart=c["dist_word_chart"],
        dist_token_chart=c["dist_token_chart"],
        vol_rows=c["vol_df"],
        max_words=c["max_words"],
        max_tokens=c["max_tokens"],
        oversized=c["oversized"],
        top_footnotes=c["top_footnotes"],
        stubs_list=c["stubs_list"],
        footnote_gap=c["footnote_gap"],
        chapter_rows_json=json.dumps(c["chapter_rows"]),
    )


@app.route("/browse")
def browse():
    d = load_corpus()
    c = d["clean"]
    sorted_tree = sorted(c["tree"].items(), key=lambda kv: vol_sort_key(kv[0]))
    return render_template(
        "browse.html",
        tree=sorted_tree,
        pretty_vol=pretty_vol,
        summary=c["summary"],
    )


@app.route("/content/<path:subpath>")
def content(subpath):
    if not subpath.endswith(".md"):
        abort(404)
    c = load_corpus()["clean"]
    rec = next((f for f in c["all_files"] if f["path"] == subpath), None)
    if not rec:
        abort(404)
    rendered = md_lib.markdown(rec["text"], extensions=["tables", "fenced_code"])
    return render_template("_content_fragment.html", selected=rec, rendered=rendered, pretty_vol=pretty_vol)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    results = []
    for rec in load_corpus()["clean"]["all_files"]:
        text = rec["text"].lower()
        idx = text.find(q)
        if idx == -1:
            continue
        start   = max(0, idx - 80)
        end     = min(len(rec["text"]), idx + len(q) + 80)
        snippet = ("…" if start else "") + rec["text"][start:end] + ("…" if end < len(rec["text"]) else "")
        results.append({
            "path":    rec["path"],
            "volume":  rec["vol_label"],
            "part":    rec["part"].replace("_", " ").title(),
            "chapter": rec["chapter"].replace(".md", "").replace("_", " ").title(),
            "words":   rec["words"],
            "snippet": snippet,
        })
    return jsonify(results[:100])


# ── Upload routes ───────────────────────────────────────────────────────────

@app.route("/upload")
def upload():
    return render_template("upload.html")


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def _s3_key_for(filename: str, category: str, h1: str, h2: str) -> str:
    if category == "uscis" and h1 and h2:
        return f"uscis_policy_manual_clean/{_slugify(h1)}/{_slugify(h2)}/{filename}"
    return S3_UPLOAD_PREFIX + filename


@app.route("/v1/uploads/presign", methods=["POST"])
def presign():
    body     = request.get_json()
    filename = body["filename"]
    category = body.get("category", "other")
    h1       = body.get("h1", "")
    h2       = body.get("h2", "")
    key      = _s3_key_for(filename, category, h1, h2)
    url      = _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": os.environ["S3_BUCKET"], "Key": key, "ContentType": "text/markdown"},
        ExpiresIn=300,
    )
    return jsonify({"url": url, "key": key})


@app.route("/v1/uploads/notify", methods=["POST"])
def notify():
    body     = request.get_json()
    key      = body["key"]
    category = body.get("category", "other")
    sqs      = boto3.client("sqs", region_name=os.environ["AWS_REGION"])
    sqs.send_message(
        QueueUrl    = os.environ["SQS_QUEUE_URL"],
        MessageBody = json.dumps({"s3_key": key, "category": category}),
    )
    _s3_cache.clear()
    return jsonify({"ok": True})


@app.route("/upload/files")
def upload_files():
    s3        = _s3_client()
    bucket    = os.environ["S3_BUCKET"]
    paginator = s3.get_paginator("list_objects_v2")
    files = []
    for prefix, category in [(S3_UPLOAD_PREFIX, "other"), (S3_CLEAN_PREFIX, "uscis")]:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".md"):
                    files.append({
                        "key":           obj["Key"],
                        "filename":      obj["Key"].split("/")[-1],
                        "category":      category,
                        "size":          obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    })
    return jsonify(sorted(files, key=lambda f: f["last_modified"], reverse=True)[:50])


# ── S3 Dashboard routes ──────────────────────────────────────────────────────

@app.route("/s3/")
def s3_dashboard():
    d = load_s3_corpus()
    return render_template(
        "s3_dashboard.html",
        summary=d["summary"],
        dist_word_chart=d["dist_word_chart"],
        dist_token_chart=d["dist_token_chart"],
        vol_rows=d["vol_df"],
        max_words=d["max_words"],
        max_tokens=d["max_tokens"],
        oversized=d["oversized"],
        chapter_rows_json=json.dumps(d["chapter_rows"]),
    )


@app.route("/s3/browse")
def s3_browse():
    d           = load_s3_corpus()
    sorted_tree = sorted(d["tree"].items(), key=lambda kv: vol_sort_key(kv[0]))
    return render_template("s3_browse.html", tree=sorted_tree, pretty_vol=pretty_vol, summary=d["summary"])


@app.route("/s3/content/<path:subpath>")
def s3_content(subpath):
    if not subpath.endswith(".md"):
        abort(404)
    d   = load_s3_corpus()
    rec = next((f for f in d["all_files"] if f["path"] == subpath), None)
    if not rec:
        abort(404)
    rendered = md_lib.markdown(rec["text"], extensions=["tables", "fenced_code"])
    return render_template("_content_fragment.html", selected=rec, rendered=rendered, pretty_vol=pretty_vol)


@app.route("/s3/search")
def s3_search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    results = []
    for rec in load_s3_corpus()["all_files"]:
        text = rec["text"].lower()
        idx  = text.find(q)
        if idx == -1:
            continue
        start   = max(0, idx - 80)
        end     = min(len(rec["text"]), idx + len(q) + 80)
        snippet = ("…" if start else "") + rec["text"][start:end] + ("…" if end < len(rec["text"]) else "")
        results.append({
            "path":    rec["path"],
            "volume":  rec["vol_label"],
            "part":    rec["part"].replace("_", " ").title(),
            "chapter": rec["chapter"].replace(".md", "").replace("_", " ").title(),
            "words":   rec["words"],
            "snippet": snippet,
        })
    return jsonify(results[:100])


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ["PORT"]))
