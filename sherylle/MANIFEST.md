# MP-16767 staging fixtures — Sherylle's own product images (prepared 2026-10-16)

Base URL (byte-stable, never re-encodes): `https://raw.githubusercontent.com/luanndbl/mallplus-uat-fixtures-mp16767/main/sherylle/<file>`
"Unchanged" = S3 object byte-identical to the file here; check with a HEAD on the stored stage-cdn URL and read `cf-polished: orig_size=<N>` (= S3 bytes), never the CDN content-length. 1 MB = 1,048,576 bytes.

| TC | File | Format | Pixels | Bytes | SHA-256 (first 12) | Expected after save |
|---|---|---|---|---|---|---|
| TC01/02 | LargeJPG.jpg | JPEG | 4000×3000 | 2,635,062 | e693ad078cd6 | 2000×1500 JPEG, smaller, upright |
| TC03 | performance_1254x1254.png | PNG (opaque RGB) | 1254×1254 | 1,287,919 | 0f7e283d7ff6 | JPEG under 1,048,576 B, `.jpg` URL, image/jpeg |
| TC03 | LargePNGSolidBG.png | PNG (opaque RGB) | 1254×1254 | 1,119,210 | 3658eaa6f0e6 | same as above |
| TC03 | PS5-Console-and-Accessories-Showcase-2.png | PNG (opaque RGB) | 1536×1024 | 1,384,535 | 2c5cbc173fbc | JPEG under 1 MB, `.jpg` |
| TC04 | SmallJPG.jpg | JPEG | 900×600 | 41,172 | 59c8243d2939 | unchanged (orig_size=41172) |
| TC04 | SmallPNG.png | PNG (opaque RGB) | 900×600 | 447,125 | ee5917eb0cb8 | unchanged, stays PNG |
| TC04 | ExactLimitJPG.jpg | JPEG | 2000×3000 | 599,382 | 798b9a2c7d71 | unchanged (height over 2000 alone does not trigger) |
| TC04 | ExactLimit-1048576-bytes-2000x3000.jpg | JPEG (padded with COM segments) | 2000×3000 | 1,048,576 exactly | c5fecf986284 | unchanged (exactly at the limit is "within limits") |
| TC05-A | NarrowTallBel1.jpg | JPEG | 800×6000 | 489,058 | 76998a82b9ba | unchanged |
| TC05-B | NarrowTallAbove1.2.jpg | JPEG | 800×6000 | 3,554,803 | 67cd58b086b1 | still 800×6000, re-encoded under 1,048,576 B, text readable |
| TC06 | WideTall.jpg | JPEG | 2400×10000 | 2,148,696 | 7e3f08f6e5d4 | about 2000×8333, smaller |
| TC07 | LargeJPG-exif-orientation-6.jpg (v2, 2026-10-16 17:40) | JPEG, pixels stored sideways 3000×4000 + EXIF Orientation=6 (viewers show it upright 4000×3000) | 3000×4000 stored / 4000×3000 upright | 945,162 | 841a73fc9361 | stored UPRIGHT 2000×1500 (width measured after rotation), EXIF removed, under 1 MB |
| TC07 | SmallJPG-exif-orientation-6.jpg (v2, 2026-10-16 17:40) | JPEG, pixels stored sideways 600×900 + EXIF Orientation=6 (viewers show it upright 900×600) | 600×900 stored / 900×600 upright | 65,500 | 2183510f7bd7 | stored UPRIGHT 900×600, EXIF removed, re-encoded even though small (rotation wins) |
| TC08 | playstation_transparent_small.png | PNG RGBA | 650×750 | 168,081 | 574479b913e7 | unchanged PNG, transparency intact |
| TC08 | playstation_transparent_large.png | PNG RGBA | 2200×2400 | 653,779 | 6f1a87d486fc | stays PNG with transparency, width stepped to 2000 or less (never below 600); if still over 1 MB at the floor the original bytes are kept |
| TC09 | webp_1536x1024_under_1MB.webp | WebP (lossy) | 1536×1024 | 23,200 | 3972886e4bcd | unchanged (WebP is not re-encoded) |
| TC10 | ../corrupt-header-2mb.jpg (repo root) | corrupt JPEG | — | — | — | original bytes kept, failure logged, image not expected to display |
| TC13 | performance_2000x1500.jpg | JPEG | 2000×1500 | 2,503,134 | 133e7c9e4321 | re-encoded under 1 MB, 2000×1500 |
| TC13 | performance_1254x1254.png | PNG | 1254×1254 | 1,287,919 | 0f7e283d7ff6 | JPEG under 1 MB |
| TC13 | performance_tall_1667x16148.jpg | JPEG | 1667×16148 (26.9 MP) | 1,769,133 | e660d02de4b6 | either re-encoded under 1 MB at 1667×16148, or (accepted fallback, open item #26) stored unchanged and logged when the JPEG decoder refuses it for memory |
| TC14 | NarrowTallAbove1.png | PNG | 800×6000 | 14,410,836 | 6699217c64cf | REJECTED by the existing 5 MB upload limit / fetch caps before any shrink (existing validation unchanged) |
| TC14 / TC11 | option_picture_over_2MB.jpg | JPEG | 2000×2000 | 10,513,400 | bc278d0bd7ac | REJECTED by the existing size limit (over 5 MB); not a shrink case |

Not coverable with product photos (developer-side fixtures): TC10 "header declaring over 40 MP" and "recompressed result larger than the input"; TC11 "variation image still over 2 MB after processing" (the ladder brings any photo under 40 MP below 1 MB, so this needs a synthetic noise image); TC09 AVIF / animated GIF (backend tests).

**TC07 note (2026-10-16 17:40):** the first EXIF-6 variants were wrong on our side: they carried an Orientation=6 tag on pixels that were already upright, so the server correctly rotated them and the result looked sideways on staging (c.83647). The files above are rebuilt with the pixels pre-rotated, so after the server bakes the rotation the picture is upright. Expected now: large → 2000×1500 upright (landscape source), small → 900×600 upright.

**TC10 developer-side fixtures (added 2026-10-19 12:40 VNT):** the two scenarios product photos cannot cover. Expected result for both = the stored S3 object is byte-identical to the file here (HEAD `cf-polished: orig_size` or a download SHA-256); the fallback / budget log line is server-side and is proven by the backend unit tests `unit-tests/api/utils/product-image-cap.spec.ts` (T5.9 (ii) header 30000x30000 → over_decode_budget; T5.7c flat 2600x1400 PNG → not_smaller) and the HTTP integration test T6.2b (corrupt bytes stored identical).

| TC | File | Format | Pixels | Bytes | SHA-256 (first 12) | Expected after save |
|---|---|---|---|---|---|---|
| TC10 (dev-side) | header-declares-30000x30000.png | PNG | 256×256 pixels, header 30000×30000 | 60,265 | 5e4609c72423 | stored unchanged (byte-identical), not decoded: the header says 30000×30000 = 900 MP, over the 40 MP decode budget; the server logs reason=over_decode_budget. The file will not display (its pixel data is only 256×256); that is expected |
| TC10 (dev-side) | flat-screenshot-2600x1400.png | PNG | 2600×1400 flat UI screenshot | 20,609 | 252c47874409 | stored unchanged as PNG (byte-identical, still 2600×1400): the server tries a 2000×1077 JPEG, it is LARGER than this tiny PNG, so the original is kept (reason=not_smaller) |
