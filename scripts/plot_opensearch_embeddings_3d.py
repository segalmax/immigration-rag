"""
Sample chunk vectors from OpenSearch (same index as /ask), reduce to 3D (UMAP+PCA like closed-book-copilot
visualize/plot_embeddings.py), write interactive Plotly HTML under data/visualizations/.

  python scripts/plot_opensearch_embeddings_3d.py
  python scripts/plot_opensearch_embeddings_3d.py --max-chunks 1500 --color-by category

Requires .env: AWS_REGION, OS_HOST, OS_INDEX (same as app/worker).
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

import dotenv
import numpy
import pandas
import plotly.express
import requests
import sklearn.decomposition

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

dotenv.load_dotenv(_REPO / ".env", override=True)

import src.opensearch_utils


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="3D embedding visualization from OpenSearch vectors.")
    p.add_argument("--max-chunks", type=int, default=2500, dest="max_chunks", help="Cap rows sampled from index")
    p.add_argument("--batch-size", type=int, default=500, dest="batch_size", help="search_after page size")
    p.add_argument("--color-by", type=str, default="volume", choices=("category", "volume"), dest="color_by")
    p.add_argument("--tag", type=str, default="default", help="Filename tag")
    p.add_argument("--no-umap", action="store_true", dest="no_umap", help="PCA only (faster, fewer deps)")
    return p.parse_args()


def _endpoint() -> str:
    return f"https://{os.environ['OS_HOST']}".rstrip("/")


def _index() -> str:
    return os.environ["OS_INDEX"]


def _vol_sort_key(slug: str) -> int:
    match = re.search(r"_(\d+)_", slug)
    return int(match.group(1)) if match else 999


def _pretty_volume(slug: str) -> str:
    if not slug or slug == "unknown":
        return "unknown"
    parts = slug.split("_")
    nums = [i for i, part in enumerate(parts) if part.isdigit()]
    if nums:
        number = parts[nums[0]]
        rest = " ".join(part.capitalize() for part in parts[nums[0] + 1 :])
        return f"Vol {number} – {rest}"
    return slug.replace("_", " ").title()


def _search_after_collect(endpoint: str, index: str, auth, max_chunks: int, batch_size: int) -> tuple[list, list]:
    """OpenSearch Serverless does not support the scroll API (404 on /_search/scroll); use search_after."""
    fields = ["vector", "s3_key", "section_path", "category", "volume", "part", "text"]
    url = f"{endpoint}/{index}/_search"
    vectors: list[list[float]] = []
    rows: list[dict] = []
    total = 0
    search_after = None
    while total < max_chunks:
        page = min(batch_size, max_chunks - total)
        if page <= 0:
            break
        payload: dict = {
            "size": page,
            "query": {"match_all": {}},
            "_source": fields,
            "sort": [{"_id": "asc"}],
        }
        if search_after is not None:
            payload["search_after"] = search_after
        response = requests.post(url, auth=auth, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            if total >= max_chunks:
                break
            src = h.get("_source") or {}
            vec = src.get("vector")
            if not vec or not isinstance(vec, list):
                continue
            vectors.append([float(x) for x in vec])
            text = (src.get("text") or "")[:220]
            if len((src.get("text") or "")) > 220:
                text += "…"
            rows.append({
                "s3_key": src.get("s3_key") or "",
                "section_path": src.get("section_path") or "",
                "category": (src.get("category") or "unknown") or "unknown",
                "volume": (src.get("volume") or "unknown") or "unknown",
                "part": src.get("part") or "",
                "Snippet": text,
            })
            total += 1
        search_after = hits[-1].get("sort")
        if search_after is None or len(hits) < page:
            break
    return vectors, rows


def _reduce_3d(vectors: numpy.ndarray, use_umap: bool) -> numpy.ndarray:
    if use_umap:
        import umap
        reducer = umap.UMAP(n_components=3, random_state=42, metric="cosine")
        emb = reducer.fit_transform(vectors)
        pca = sklearn.decomposition.PCA(n_components=3, random_state=42)
        return pca.fit_transform(emb)
    pca = sklearn.decomposition.PCA(n_components=3, random_state=42)
    return pca.fit_transform(vectors)


def main() -> None:
    args = parse_args()
    out_dir = _REPO / "data" / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamp_html = out_dir / f"embeddings_3d_{ts}_{args.tag}.html"
    latest_html = out_dir / "embeddings_3d_latest.html"

    endpoint = _endpoint()
    index = _index()
    auth = src.opensearch_utils.OPENSEARCH_HTTP_AUTH

    print(f"Fetching {index} (search_after, max {args.max_chunks} chunks, batch {args.batch_size})…")
    vectors_list, meta = _search_after_collect(endpoint, index, auth, args.max_chunks, args.batch_size)
    if len(vectors_list) < 10:
        raise RuntimeError(f"Too few vectors with numeric embedding: got {len(vectors_list)}, need OpenSearch data.")

    vectors = numpy.asarray(vectors_list, dtype=numpy.float64)
    dim = vectors.shape[1]
    use_umap = not args.no_umap
    if use_umap:
        try:
            import umap  # noqa: F401
        except ImportError:
            print("umap-learn not installed; using PCA only. pip install umap-learn for closed-book-style UMAP+PCA.")
            use_umap = False

    print(f"Reducing {vectors.shape[0]} x {dim} to 3D ({'UMAP+PCA' if use_umap else 'PCA only'})…")
    projections = _reduce_3d(vectors, use_umap)

    color_key = args.color_by
    category_orders: dict | None = None
    for i, row in enumerate(meta):
        row["x"] = float(projections[i, 0])
        row["y"] = float(projections[i, 1])
        row["z"] = float(projections[i, 2])
        if color_key == "volume":
            row["Color"] = _pretty_volume(row.get("volume") or "unknown")
        else:
            row["Color"] = row.get("category") or "unknown"

    if color_key == "volume":
        slugs = sorted({(r.get("volume") or "unknown") for r in meta}, key=_vol_sort_key)
        category_orders = {"Color": [_pretty_volume(s) for s in slugs]}

    df = pandas.DataFrame(meta)
    subtitle = f"Index: {index} | Chunks: {len(meta)} | Vector dim: {dim} | Reduction: {'UMAP+PCA' if use_umap else 'PCA'} | Color: {color_key}"

    fig = plotly.express.scatter_3d(
        df,
        x="x",
        y="y",
        z="z",
        color="Color",
        hover_data=["section_path", "s3_key", "category", "volume", "Snippet"],
        title=f"OpenSearch chunk embeddings (3D)<br><sup>{subtitle}</sup>",
        opacity=0.7,
        color_discrete_sequence=plotly.express.colors.qualitative.Dark24,
        category_orders=category_orders,
    )
    fig.update_traces(marker={"size": 4})
    fig.update_layout(
        scene={
            "camera": {
                "eye": {"x": 1.5, "y": 1.5, "z": 1.2},
                "center": {"x": 0, "y": 0, "z": 0},
                "up": {"x": 0, "y": 0, "z": 1},
            }
        }
    )

    fig.write_html(str(stamp_html))
    fig.write_html(str(latest_html))
    meta_path = out_dir / f"embeddings_3d_{ts}_{args.tag}.json"
    meta_path.write_text(
        json.dumps({"html": stamp_html.name, "latest": latest_html.name, "subtitle": subtitle}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {stamp_html}")
    print(f"Wrote {latest_html} (served at /embeddings-3d when Flask runs)")
    print(f"Metadata {meta_path}")


if __name__ == "__main__":
    main()
