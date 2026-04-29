import asyncio
import os
import zipfile
from pathlib import Path
from playwright.async_api import async_playwright

BASE = Path("/home/user/zubamx")
ADS = BASE / "ads"
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# (html_path, output_name, width, height, is_pdf)
ASSETS = [
    # ── Prioridad 1 — Flyers pauta Meta (PNG 1080x1080)
    (ADS / "flyer-segmento-a.html",               "ZUBA_Flyer_SegmentoA_1080x1080.png",         1080, 1080, False),
    (ADS / "flyer-segmento-b.html",               "ZUBA_Flyer_SegmentoB_1080x1080.png",         1080, 1080, False),

    # ── Prioridad 1 — Scripts video (PDF)
    (ADS / "video-script-segmento-a.html",        "ZUBA_VideoScript_SegmentoA.pdf",             1000, None, True),
    (ADS / "video-script-segmento-b.html",        "ZUBA_VideoScript_SegmentoB.pdf",             1000, None, True),

    # ── Prioridad 2 — Posts Facebook Seg B (PNG 1080x1080)
    (ADS / "posts-segmento-b/post-b1-competencia.html", "ZUBA_Post_B1_Competencia_1080x1080.png", 1080, 1080, False),
    (ADS / "posts-segmento-b/post-b2-entrar-mal.html",  "ZUBA_Post_B2_EntrarMal_1080x1080.png",  1080, 1080, False),
    (ADS / "posts-segmento-b/post-b3-primer-dia.html",  "ZUBA_Post_B3_PrimerDia_1080x1080.png",  1080, 1080, False),
    (ADS / "posts-segmento-b/post-b4-pregunta.html",    "ZUBA_Post_B4_Pregunta_1080x1080.png",   1080, 1080, False),

    # ── Prioridad 2 — Posts grupos (PDF)
    (ADS / "posts-segmento-b/posts-grupos-segmento-b.html", "ZUBA_PostsGrupos_SegmentoB.pdf",    1000, None, True),

    # ── Prioridad 2 — TikTok script (PDF)
    (ADS / "posts-segmento-b/tiktok-script-segmento-b.html", "ZUBA_TikTok_Script_SegmentoB.pdf", 1000, None, True),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for html_path, out_name, width, height, is_pdf in ASSETS:
            print(f"  → {out_name}")
            out_file = OUT / out_name

            if is_pdf:
                page = await browser.new_page(viewport={"width": width, "height": 900})
                await page.goto(f"file://{html_path}")
                await page.wait_for_timeout(300)
                await page.pdf(
                    path=str(out_file),
                    print_background=True,
                    format="A4",
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            else:
                page = await browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=2,   # retina → mayor resolución
                )
                await page.goto(f"file://{html_path}")
                await page.wait_for_timeout(300)
                await page.screenshot(
                    path=str(out_file),
                    full_page=False,
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                )

            await page.close()

        await browser.close()

    # ── ZIP
    zip_path = BASE / "ZUBA_KIT_ADS.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.iterdir()):
            zf.write(f, f.name)
    print(f"\n✓ ZIP listo: {zip_path}")
    print(f"  Archivos incluidos: {len(list(OUT.iterdir()))}")

asyncio.run(main())
