"""
kb_dashboard/app.py
Flask dev dashboard for inspecting the USCIS Policy Manual knowledge base.
Runs locally only — not the production RAG API (that lives in ../app.py).
"""
import json
import re
from pathlib import Path

import markdown as md_lib
import pandas as pd
import plotly.express as px
import tiktoken
from flask import Flask, render_template, abort

app = Flask(__name__)

RAW_ROOT   = Path(__file__).parent.parent / "data" / "uscis_policy_manual"
CLEAN_ROOT = Path(__file__).parent.parent / "data" / "uscis_policy_manual_clean"

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
@app.route("/browse/<path:subpath>")
def browse(subpath=None):
    d = load_corpus()
    c = d["clean"]
    selected = rendered = None

    if subpath:
        full = CLEAN_ROOT / subpath
        if not full.exists() or not subpath.endswith(".md"):
            abort(404)
        rec = next((f for f in c["all_files"] if f["path"] == subpath), None)
        if rec:
            selected = rec
            rendered = md_lib.markdown(rec["text"], extensions=["tables","fenced_code"])

    sorted_tree = sorted(c["tree"].items(), key=lambda kv: vol_sort_key(kv[0]))
    return render_template(
        "browse.html",
        tree=sorted_tree,
        pretty_vol=pretty_vol,
        selected=selected,
        rendered=rendered,
        subpath=subpath or "",
        summary=c["summary"],
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)
