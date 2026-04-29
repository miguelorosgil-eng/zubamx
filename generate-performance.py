import asyncio, zipfile
from pathlib import Path
from playwright.async_api import async_playwright

BASE = Path("/home/user/zubamx")
PERF = BASE / "ads/performance"
OUT  = BASE / "output/performance"
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = [
    # V1 — Agresiva
    ("v1-agresiva-feed.html",      "V1_Agresiva_Feed_1080x1350.png",     1080, 1350),
    ("v1-agresiva-stories.html",   "V1_Agresiva_Stories_1080x1920.png",  1080, 1920),
    # V2 — Aspiracional
    ("v2-aspiracional-feed.html",  "V2_Aspiracional_Feed_1080x1350.png", 1080, 1350),
    ("v2-aspiracional-stories.html","V2_Aspiracional_Stories_1080x1920.png",1080,1920),
    # V3 — Directa
    ("v3-directa-feed.html",       "V3_Directa_Feed_1080x1350.png",      1080, 1350),
    ("v3-directa-stories.html",    "V3_Directa_Stories_1080x1920.png",   1080, 1920),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for fname, outname, w, h in ASSETS:
            print(f"  → {outname}")
            page = await browser.new_page(
                viewport={"width": w, "height": h},
                device_scale_factor=2,
            )
            await page.goto(f"file://{PERF / fname}")
            await page.wait_for_timeout(400)
            await page.screenshot(
                path=str(OUT / outname),
                full_page=False,
                clip={"x": 0, "y": 0, "width": w, "height": h},
            )
            await page.close()
        await browser.close()

    zip_path = BASE / "ZUBA_KIT_PERFORMANCE_ADS.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.iterdir()):
            zf.write(f, f"performance/{f.name}")
    print(f"\n✓ ZIP listo: {zip_path}")
    for f in sorted(OUT.iterdir()):
        size_kb = f.stat().st_size // 1024
        print(f"   {f.name}  ({size_kb} KB)")

asyncio.run(main())
