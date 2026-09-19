"""
Standalone test for Hugging Face image generation.

Does NOT touch the pipeline, the graph, or Facebook.
Just calls the HF adapter directly and saves one image.
"""
import asyncio
from pathlib import Path

from smauto.services.media.hf_image_gen import generate_image_hf


async def main():
    out = Path("runs/_test/hf_test.png")
    print("Calling Hugging Face...")
    print("  model:", "black-forest-labs/FLUX.1-schnell")
    print("  output:", out)
    print()

    result = await generate_image_hf(
        prompt=(
            "Minimalist editorial illustration for a social media post "
            "about customer support costs. Dark navy background, one bold "
            "cyan geometric shape, subtle grain, no text, no words, "
            "no letters, no logos."
        ),
        out_path=out,
        width=1024,
        height=1024,
    )

    size = result.stat().st_size
    print()
    print(f"✅ Image saved: {result}")
    print(f"   size: {size:,} bytes ({size/1024:.1f} KB)")
    print()
    print("Open it:")
    print(f"   start {result}")


if __name__ == "__main__":
    asyncio.run(main())