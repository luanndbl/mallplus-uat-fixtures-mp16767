#!/usr/bin/env python3
"""MP-16767 TC13 / AC-6 - N parallel seller product-image uploads + /health poll.

Standard library only (Python 3.8+). Two modes:

  upload  - presign -> PUT the real bytes -> commit to a product, N requests in parallel.
            Each worker is one upload: POST /vendor/uploads/presigned-multi-urls,
            PUT <presigned url>, then POST /vendor/products/<id> with the temp URL as
            images[0] (+ thumbnail). The commit is the step that runs the MP-16767 cap.
  health  - GET /health every 0.5 s and record the response time (ms). Run it in a
            second terminal for the whole upload window; it prints p50 / p95 / max.

Examples (staging):
  export SELLER_JWT='eyJ...'            # Seller Center -> DevTools -> Authorization header of any /vendor call
  python3 tc13_parallel_upload.py health --api https://staging-api.mallplus.ph --out health-a.csv
  python3 tc13_parallel_upload.py upload --api https://staging-api.mallplus.ph \
      --products prod_01M51XEKX8S0EBY7976C70EKS3 --file performance_2000x1500.jpg --count 20 --out batch-a.csv

Batches from the perf review (AC-6):
  (a) 20 x performance_2000x1500.jpg     (b) 20 x performance_1254x1254.png
  (c) 4 x performance_tall_1667x16148.jpg (d) 1 x performance_tall_1667x16148.jpg
Pass thresholds: (a)/(b) /health p95 <= 500 ms, max <= 1 s; (c)/(d) /health max <= 3 s, one upload <= 10 s.

Notes
- Every request in a batch commits to the products given in --products (round-robin). With one product,
  the 20 commits race on the same images[] array (last writer wins); every upload is still processed,
  which is what the load test measures. Use a throw-away test product.
- Only the seller JWT you pass is used; nothing else is read or written.
"""
import argparse
import concurrent.futures as cf
import csv
import json
import mimetypes
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

FILE_TYPE = "VENDOR_PRODUCT_IMAGE"


def http(method, url, body=None, headers=None, timeout=120):
    data = None
    hdrs = dict(headers or {})
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif isinstance(body, (bytes, bytearray)):
        data = body
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, raw, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read(), (time.perf_counter() - t0) * 1000
    except (urllib.error.URLError, OSError) as e:  # connection reset / timeout / no VPN
        return 0, str(e).encode(), (time.perf_counter() - t0) * 1000


def one_upload(i, api, token, product_id, path, mime, size, data):
    auth = {"Authorization": f"Bearer {token}"}
    name = f"tc13-{int(time.time())}-{i:02d}-{os.path.basename(path)}"
    row = {"n": i, "product": product_id, "file": os.path.basename(path), "bytes": size}
    t_start = time.perf_counter()

    # 1. presign (declares the real size; this is also where MP-16506's first gate runs)
    st, raw, ms = http("POST", f"{api}/vendor/uploads/presigned-multi-urls",
                       {"files": [{"originalname": name, "mime_type": mime, "size": size, "file_type": FILE_TYPE}]},
                       auth)
    row["presign_status"], row["presign_ms"] = st, round(ms)
    if st != 200:
        row["error"] = raw[:300].decode(errors="replace")
        return row
    slot = json.loads(raw)
    slot = (slot.get("files") or slot.get("presigned_urls") or slot.get("data") or slot)
    if isinstance(slot, dict) and "url" not in slot:
        slot = next(iter(v for v in slot.values() if isinstance(v, list)), [slot])
    slot = slot[0] if isinstance(slot, list) else slot
    put_url, file_path = slot["url"], slot.get("file_path", "")
    # the Seller Center stores file_path when it is a full URL, else the presigned URL without its query
    commit_url = file_path if file_path.startswith("http") else put_url.split("?")[0]

    # 2. PUT the real bytes
    st, raw, ms = http("PUT", put_url, data, {"Content-Type": mime}, timeout=300)
    row["put_status"], row["put_ms"] = st, round(ms)
    if st not in (200, 201, 204):
        row["error"] = raw[:300].decode(errors="replace")
        return row

    # 3. commit: the product save moves temp -> vd-pdimg and runs the MP-16767 cap
    st, raw, ms = http("POST", f"{api}/vendor/products/{product_id}",
                       {"images": [{"url": commit_url}], "thumbnail": commit_url}, auth, timeout=300)
    row["commit_status"], row["commit_ms"] = st, round(ms)
    row["total_ms"] = round((time.perf_counter() - t_start) * 1000)
    if st == 200:
        try:
            p = json.loads(raw).get("product", {})
            imgs = [im.get("url") for im in p.get("images", [])]
            row["stored_url"] = next((u for u in imgs if u and os.path.basename(path).rsplit(".", 1)[0][:20] in u), imgs[0] if imgs else "")
        except Exception:
            row["stored_url"] = ""
    else:
        row["error"] = raw[:300].decode(errors="replace")
    return row


def cmd_upload(a):
    token = a.token or os.environ.get("SELLER_JWT")
    if not token:
        sys.exit("seller JWT missing: --token or SELLER_JWT")
    data = open(a.file, "rb").read()
    mime = mimetypes.guess_type(a.file)[0] or "application/octet-stream"
    products = [p.strip() for p in a.products.split(",") if p.strip()]
    print(f"{a.count} parallel uploads of {a.file} ({len(data)} B, {mime}) -> {a.api}  products={products}")
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=a.count) as ex:
        rows = list(ex.map(lambda i: one_upload(i, a.api, token, products[i % len(products)], a.file, mime, len(data), data),
                           range(1, a.count + 1)))
    wall = time.perf_counter() - t0
    keys = ["n", "product", "file", "bytes", "presign_status", "presign_ms", "put_status", "put_ms",
            "commit_status", "commit_ms", "total_ms", "stored_url", "error"]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r.get("commit_status") == 200]
    tot = [r["total_ms"] for r in rows if "total_ms" in r]
    print(f"wall {wall:.1f}s | commits 200: {len(ok)}/{len(rows)} | per-upload total ms: "
          f"min {min(tot) if tot else '-'} p50 {round(statistics.median(tot)) if tot else '-'} max {max(tot) if tot else '-'}")
    for r in rows:
        if r.get("error"):
            print(f"  #{r['n']} FAILED: presign={r.get('presign_status')} put={r.get('put_status')} commit={r.get('commit_status')} {r['error'][:160]}")
    print(f"rows -> {a.out}")


def cmd_health(a):
    url = f"{a.api}/health"
    print(f"polling {url} every {a.interval}s, Ctrl-C to stop (writes {a.out})")
    samples = []
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iso_time", "status", "ms"])
        try:
            while True:
                st, _, ms = http("GET", url, timeout=30)
                samples.append(ms)
                w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), st, round(ms)])
                f.flush()
                if ms > a.warn_ms or st != 200:
                    print(f"  {time.strftime('%H:%M:%S')} /health {st} {round(ms)} ms")
                time.sleep(max(0.0, a.interval - ms / 1000))
        except KeyboardInterrupt:
            pass
    if samples:
        s = sorted(samples)
        p = lambda q: round(s[min(len(s) - 1, int(q * len(s)))])
        print(f"/health samples {len(s)} | p50 {p(0.50)} ms | p95 {p(0.95)} ms | max {round(s[-1])} ms")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("upload")
    u.add_argument("--api", default="https://staging-api.mallplus.ph")
    u.add_argument("--token", help="seller JWT (or env SELLER_JWT)")
    u.add_argument("--products", required=True, help="product id(s), comma separated, round-robin")
    u.add_argument("--file", required=True, help="fixture to upload")
    u.add_argument("--count", type=int, default=20)
    u.add_argument("--out", default="tc13-uploads.csv")
    u.set_defaults(fn=cmd_upload)
    h = sub.add_parser("health")
    h.add_argument("--api", default="https://staging-api.mallplus.ph")
    h.add_argument("--interval", type=float, default=0.5)
    h.add_argument("--warn-ms", type=int, default=500)
    h.add_argument("--out", default="tc13-health.csv")
    h.set_defaults(fn=cmd_health)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
