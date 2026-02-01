#!/usr/bin/env python3
"""
Camellia cultivar enrichment script.

Reads unenriched rows from genes_combined.csv, researches each cultivar via
iflora page scraping and Claude API, and writes an intermediate CSV with the
raw Claude response in a single column for post-processing.
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.parse

import anthropic
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IFLORA_CULTIVAR_URL = "https://camellia.iflora.cn/Cutivars/Detail?latin={}"
IFLORA_SPECIES_URL = "https://camellia.iflora.cn/Species/Detail?latin={}"

OUTPUT_FIELDS = ["Cultivar", "Epithet", "Category", "Claude Response"]

CATEGORY_SPECIES = {"species", "specie", "Species", "Specie"}

# Three representative enriched examples used as few-shot context.
EXAMPLE_BLOCK = """\
--- Example 1 (Reticulata Hybrid) ---
Input: Adrian Bourres | Camellia reticulata 'Adrienne Boueres' | RH

Color / Form: Dark Pink / Rose Form Double
Description: RETICULATA HYBRID. Medium-large 10.7cm, ACS #2889 (2013). Howard & Mary Rhodes, Tallahassee FL. Seedling of 'Frank Houser', first bloomed 2008, mid-late season.
Notes: A distinguished reticulata hybrid that emerged as a chance seedling from the celebrated 'Frank Houser'. Originated by Howard and Mary Rhodes of Tallahassee, Florida, this nine-year-old seedling first revealed its impressive blooms in 2008 before being registered with the American Camellia Society in December 2013 (ACS #2889). The substantial rose form double flowers display rich dark pink petals with contrasting yellow anthers and white filaments, measuring approximately 10.7cm across. Flowers fall intact, keeping the garden tidy. The spreading growth habit and handsome mid-green foliage make it suitable for both exhibition and landscape use. Blooms mid to late season. (Source: International Camellia Register)
Image URL: https://camellia.iflora.cn/Cutivars/Detail?latin=Adrienne+Boueres

--- Example 2 (Sasanqua) ---
Input: Asakura | Camellia sasanqua 'Asakura' | S

Color / Form: White with Pale Red shading / Semi-double to Double
Description: Large flowers with waxy petals; tall upright form; Kurume, Fukuoka Prefecture, Japan; fall to midwinter bloom.
Notes: Asakura is a Japanese sasanqua camellia originating from the Kurume region of Fukuoka Prefecture, a legendary center of camellia breeding in Japan. The cultivar produces large white flowers with delicate pale red shading and many golden stamens, carried on an upright plant with glossy dark green, toothed-margin leaves on thin wiry stems. Blooming from fall through midwinter, it demonstrates the hardier nature of sasanqua types, making it suitable for hedges, borders, and specimen plantings. Exemplifies the sophisticated breeding work characteristic of Kurume camellias. (Source: International Camellia Register)
Image URL: https://camellia.iflora.cn/Cutivars/Detail?latin=Asakura

--- Example 3 (Species) ---
Input: Camellia gauchoweninsis | Camellia gauchowensis | Species

Color / Form: White / Single
Description: SPECIES. Medium 6-7.5cm; slightly fragrant; 5-8 obovate petals; evergreen shrub or small tree 2-8m; native to Guangdong, China; Section Oleifera; now synonymized under C. drupifera.
Notes: Camellia gauchowensis Hung T.Chang (now treated as a synonym of Camellia drupifera Lour.) is an evergreen shrub or small tree growing 2-8 meters tall, native to southwestern Guangdong Province and southern Guangxi in China. First described in 1961 by Chang Hung-ta. The species produces solitary, slightly fragrant white flowers 6-7.5cm in diameter with 5-8 obovate petals, blooming December to January. One of China's most important oil-tea camellia species. Hardy to USDA Zone 9. (Source: International Camellia Register and Flora of China)
Image URL: https://camellia.iflora.cn/Species/Detail?latin=Camellia+gauchowensis
"""

# ---------------------------------------------------------------------------
# iflora scraping helpers
# ---------------------------------------------------------------------------

def _iflora_url(epithet: str, category: str) -> str:
    """Build the iflora URL for a cultivar or species."""
    if category.strip() in CATEGORY_SPECIES:
        latin = epithet.strip()
        return IFLORA_SPECIES_URL.format(urllib.parse.quote(latin, safe=""))
    else:
        m = re.search(r"'(.+)'", epithet)
        latin = m.group(1) if m else epithet.strip()
        return IFLORA_CULTIVAR_URL.format(urllib.parse.quote(latin, safe=""))


def fetch_iflora(epithet: str, category: str, timeout: int = 15) -> str:
    """Fetch and return trimmed text from the iflora page."""
    url = _iflora_url(epithet, category)
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; CamelliaResearchBot/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"[iflora fetch failed: {exc}]"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if len(text) > 8000:
        text = text[:8000] + "\n... [truncated]"
    return text


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a botanical researcher specializing in Camellia cultivars. Given scraped \
reference data and an input row, produce enrichment information for this cultivar.

Include ALL of the following in your response:
- Color / Form: Standard color(s) + "/" + flower form. Use standard terms: \
White, Blush, Pink, Rose, Red, Coral, Variegated; Single, Semi-double, Anemone, \
Peony, Rose-form Double, Formal Double. Use "Unknown / Unknown" only as last resort.
- Description: Compact semi-colon-separated facts. Start with category label for \
hybrids/species (e.g. "RETICULATA HYBRID." or "SPECIES."). Include: flower size, \
originator/location/year, parentage, bloom season, growth habit, awards.
- Notes: 3-6 sentence prose paragraph. Start with cultivar name. Include history, \
appearance, significance. End with "(Source: ...)" citation.
- Image URL: The iflora page URL (cultivar or species). Leave blank if not found.

If the cultivar cannot be found in any source, set Color / Form to \
"Unknown / Unknown", Description to "Limited information available …", and Notes \
to a paragraph explaining the search was unsuccessful, ending with \
"(Limited information available)".

Format your response with labeled lines:
Color / Form: <value>
Description: <value>
Notes: <value>
Image URL: <value>
"""


def enrich_with_claude(
    client: anthropic.Anthropic,
    cultivar: str,
    epithet: str,
    category: str,
    iflora_text: str,
    model: str = "claude-sonnet-4-20250514",
    use_web_search: bool = False,
) -> str:
    """Call Claude and return the raw response text."""
    user_content = (
        f"## Reference examples (match this style)\n\n"
        f"{EXAMPLE_BLOCK}\n\n"
        f"## Input row\n"
        f"Cultivar: {cultivar}\n"
        f"Epithet: {epithet}\n"
        f"Category: {category}\n\n"
        f"## Scraped iflora page content\n"
        f"{iflora_text}\n\n"
        f"Now produce the enrichment information for this cultivar."
    )

    kwargs: dict = dict(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    if use_web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

    response = client.messages.create(**kwargs)

    # Extract all text blocks from the response
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# CSV I/O helpers
# ---------------------------------------------------------------------------

def read_input_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def read_existing_cultivars(path: str) -> set[str]:
    """Return set of cultivar names already in the output."""
    names: set[str] = set()
    if not os.path.exists(path):
        return names
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Cultivar", "").strip()
            if name:
                names.add(name)
    return names


def append_row(output_path: str, row: dict):
    """Append a single row to the output CSV."""
    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Enrich camellia cultivar CSV via iflora scraping + Claude API"
    )
    parser.add_argument(
        "--input", default="genes_combined.csv",
        help="Source CSV (default: genes_combined.csv)",
    )
    parser.add_argument(
        "--output", default="genes_intermediate.csv",
        help="Intermediate output CSV (default: genes_intermediate.csv)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max rows to process this run (0 = all remaining)",
    )
    parser.add_argument(
        "--start-row", type=int, default=0,
        help="1-indexed row in input CSV to start from (0 = auto-detect)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-20250514",
        help="Claude model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds to wait between cultivars (default: 2.0)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    input_rows = read_input_csv(args.input)
    print(f"Loaded {len(input_rows)} rows from {args.input}")

    already_done = read_existing_cultivars(args.output)
    if already_done:
        print(f"Output {args.output} has {len(already_done)} rows — resuming.")

    start_idx = (args.start_row - 1) if args.start_row > 0 else 0

    processed = 0
    for i, row in enumerate(input_rows):
        if i < start_idx:
            continue

        cultivar = row.get("Cultivar", "").strip()
        epithet = row.get("Epithet", "").strip()
        category = row.get("Category", "").strip()

        if not cultivar or cultivar in already_done:
            continue

        print(f"\n[{processed + 1}] Enriching: {cultivar} (row {i + 1})")

        # Fetch iflora
        print("  Fetching iflora...")
        iflora_text = fetch_iflora(epithet, category)
        iflora_empty = (
            "fetch failed" in iflora_text.lower()
            or len(iflora_text.strip()) < 100
        )

        # Call Claude
        print("  Calling Claude API...")
        try:
            response_text = enrich_with_claude(
                client,
                cultivar=cultivar,
                epithet=epithet,
                category=category,
                iflora_text=iflora_text,
                model=args.model,
                use_web_search=iflora_empty,
            )
        except anthropic.APIError as exc:
            print(f"  API error: {exc}", file=sys.stderr)
            response_text = (
                f"Color / Form: Unknown / Unknown\n"
                f"Description: Limited information available; API error.\n"
                f"Notes: {cultivar} could not be enriched due to an API error. "
                f"Retry in a subsequent run. (Limited information available)\n"
                f"Image URL: {_iflora_url(epithet, category)}"
            )

        # Write row with raw response
        append_row(args.output, {
            "Cultivar": cultivar,
            "Epithet": epithet,
            "Category": category,
            "Claude Response": response_text,
        })
        already_done.add(cultivar)

        processed += 1
        # Show first line of response as progress indicator
        first_line = response_text.split("\n", 1)[0]
        print(f"  {first_line}")

        if args.limit > 0 and processed >= args.limit:
            print(f"\nReached limit of {args.limit} rows.")
            break

        if i < len(input_rows) - 1:
            time.sleep(args.delay)

    print(f"\nFinished. Processed {processed} new rows.")
    print(f"Total rows in {args.output}: {len(already_done)}")


if __name__ == "__main__":
    main()
