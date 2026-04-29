import asyncio, zipfile
from pathlib import Path
from playwright.async_api import async_playwright

BASE = Path("/home/user/zubamx")
SRC  = BASE / "ads/b2b-ads"
OUT  = BASE / "output/b2b-ads"
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = [
    ("ad1-notificaciones.html", "ZUBA_B2B_Notificaciones_1080x1350.png", 1080, 1350),
    ("ad2-comparativa.html",    "ZUBA_B2B_Comparativa_1080x1350.png",    1080, 1350),
    ("ad3-algoritmo.html",      "ZUBA_B2B_Algoritmo_1080x1350.png",      1080, 1350),
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
            await page.wait_for_timeout(500)
            await page.screenshot(
                path=str(OUT / outname),
                full_page=False,
                clip={"x": 0, "y": 0, "width": w, "height": h},
            )
            await page.close()
        await browser.close()

    zip_path = BASE / "ZUBA_KIT_B2B_ADS.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.iterdir()):
            zf.write(f, f"b2b-ads/{f.name}")
    print(f"\n✓ ZIP listo: {zip_path}")
    for f in sorted(OUT.iterdir()):
        print(f"   {f.name}  ({f.stat().st_size // 1024} KB)")

asyncio.run(main())
