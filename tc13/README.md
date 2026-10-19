# MP-16767 TC13 (AC-6) — 20 parallel uploads on staging, with the `/health` poll

Everything here is run by QA from a laptop on the VPN with a **seller** login on staging. The script uses
only the Python 3 standard library (3.8+): no install step.

## Files

| File | Use |
|---|---|
| `tc13_parallel_upload.py` | `upload` mode = N parallel presign → PUT → commit; `health` mode = `GET /health` every 0.5 s |
| `../sherylle/performance_2000x1500.jpg` | batch (a): 2000×1500 JPEG, 2,503,134 B |
| `../sherylle/performance_1254x1254.png` | batch (b): 1254×1254 opaque PNG, 1,287,919 B |
| `../sherylle/performance_tall_1667x16148.jpg` | batches (c)/(d): 1667×16148 JPEG strip (26.9 MP), 1,769,133 B |

Download: `https://raw.githubusercontent.com/luanndbl/mallplus-uat-fixtures-mp16767/main/tc13/tc13_parallel_upload.py`
and the three fixtures from `…/main/sherylle/<file>`.

## Steps

1. **Seller JWT**: log in to the staging Seller Center, open DevTools → Network, click any request to
   `staging-api.mallplus.ph/vendor/...` and copy the `Authorization: Bearer <token>` value (without `Bearer `).
   `export SELLER_JWT='<token>'` (Windows PowerShell: `$env:SELLER_JWT='<token>'`).
2. **Test product**: use a throw-away product of that seller (for example `prod_01M51XEKX8S0EBY7976C70EKS3`).
   Every commit replaces that product's `images[]`, so do not use a real listing.
3. **Terminal 1 — health poll** (start it first, keep it running for the whole batch, Ctrl-C after):
   ```
   python3 tc13_parallel_upload.py health --api https://staging-api.mallplus.ph --out health-a.csv
   ```
   It prints every sample over 500 ms as it happens and the p50 / p95 / max summary when stopped.
4. **Terminal 2 — batch (a)**:
   ```
   python3 tc13_parallel_upload.py upload --api https://staging-api.mallplus.ph \
     --products prod_01M51XEKX8S0EBY7976C70EKS3 --file performance_2000x1500.jpg --count 20 --out batch-a.csv
   ```
   Then (b) with `performance_1254x1254.png --count 20`, (c) with `performance_tall_1667x16148.jpg --count 4`,
   (d) with `performance_tall_1667x16148.jpg --count 1`. Restart the health poll with a new `--out` per batch.
5. **Record** per batch: `health-*.csv` summary (p50 / p95 / max), `batch-*.csv` (presign / PUT / commit status
   and ms per upload, wall time, stored URLs), and the stored URL of one upload per batch (HEAD on stage-cdn
   shows the shrunk result: JPEG under 1 MB for (a)/(b); the strip either re-encoded under 1 MB at 1667×16148
   or stored unchanged, open item #26).

## Pass thresholds (perf review, AC-6)

| Batch | `/health` | per upload |
|---|---|---|
| (a) 20 × 2000×1500 JPEG, (b) 20 × 1254×1254 PNG | p95 ≤ 500 ms, max ≤ 1 s | all commits 200 |
| (c) 4 × 26.9 MP strip, (d) 1 × strip | max ≤ 3 s | one commit ≤ 10 s |

## What this does not measure

Container RSS (memory) is not visible from outside the container; `/health` only shows event-loop stalls.
Memory needs DevOps (`docker stats` / the container metrics on the staging API host) during the same window;
ask Francis or Argel to capture the peak RSS while the batches run. The design bound is FR-9 (process-wide
decode/encode limiter) + FR-11 (resize before the second bitmap copy); the unit and integration suites assert
both, see the card's `test-report.md`.
