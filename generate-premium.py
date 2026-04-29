import asyncio, zipfile
from pathlib import Path
from playwright.async_api import async_playwright

BASE = Path("/home/user/zubamx")
SRC  = BASE / "ads/premium"
OUT  = BASE / "output/premium"
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = [
    ("p1-algoritmo.html",     "ZUBA_Premium_Algoritmo_1080x1350.png",     1080, 1350),
    ("p2-comparativa.html",   "ZUBA_Premium_Comparativa_1080x1350.png",   1080, 1350),
    ("p3-notificaciones.html","ZUBA_Premium_Notificaciones_1080x1350.png",1080, 1350),
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
            await page.goto(f"file://{SRC / fname}")
            await page.wait_for_timeout(800)
            await page.screenshot(
                path=str(OUT / outname),
                full_page=False,
                clip={"x": 0, "y": 0, "width": w, "height": h},
            )
            await page.close()
        await browser.close()

    zip_path = BASE / "ZUBA_KIT_PREMIUM_ADS.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.iterdir()):
            zf.write(f, f"premium/{f.name}")
    print(f"\n✓ ZIP: {zip_path}")
    for f in sorted(OUT.iterdir()):
        print(f"   {f.name}  ({f.stat().st_size // 1024} KB)")

asyncio.run(main())
