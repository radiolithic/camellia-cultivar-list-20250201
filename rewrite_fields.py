#!/usr/bin/env python3
"""
Batch rewrite tagline, description, and notes for camellia cultivars
using the Claude API. Processes 5 records per API call.

Usage:
    python3 rewrite_fields.py --dry-run --limit 5
    python3 rewrite_fields.py --limit 20
    python3 rewrite_fields.py                    # all records
    python3 rewrite_fields.py --start-id 100     # resume from id 100
    ANTHROPIC_API_KEY=sk-... python3 rewrite_fields.py --limit 5
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time

import anthropic

DB_PATH = "/var/www/genes/data/genes.db"
BATCH_SIZE = 5
DELAY_BETWEEN_CALLS = 2  # seconds
MAX_RETRIES = 3
WARNING_LOG = "/var/www/genes/rewrite_warnings.log"

SYSTEM_PROMPT = """\
You are a camellia cultivar reference writer. For each cultivar provided, produce three fields: TAGLINE, DESCRIPTION, and NOTES.

**TAGLINE**: One punchy sentence — the single most distinctive thing about this cultivar. No species name. Be specific: unusual color, award history, famous parentage, extreme hardiness, historical significance, unique form, etc. If information is sparse, focus on the most notable observable trait.

**DESCRIPTION**: A single flowing sentence covering the key facts in consistent order (omit any that are unknown): flower size and form, color, registration info, originator/location/year, parentage (for hybrids), bloom season, growth habit, awards. Natural prose — deliberately distinct from telegraphic ICR source text. Compact but readable. Do not start with the cultivar name.

**NOTES**: 3–6 sentence narrative. Do NOT open with the cultivar name or species — the epithet already carries that. Focus on: significance/role in camellia world, origin story, appearance and garden merit, awards, growing context. End with a brief source citation (e.g., "Source: International Camellia Register" or "Source: American Camellia Society"). Authoritative but accessible tone for people who know camellias.

For each cultivar, output in exactly this format:
===CULTIVAR: <name>===
TAGLINE: <one sentence>
DESCRIPTION: <one flowing sentence>
NOTES: <3-6 sentence narrative>

If you have very little information about a cultivar, do your best with what's available. Never fabricate registration numbers or specific dates you're unsure of."""


def build_user_prompt(records):
    """Build the user prompt from a batch of cultivar records."""
    parts = []
    for r in records:
        parts.append(
            f"Cultivar: {r['cultivar']}\n"
            f"Epithet: {r['epithet']}\n"
            f"Category: {r['category']}\n"
            f"Color/Form: {r['color_form']}\n"
            f"Current Description: {r['description']}\n"
            f"Current Notes: {r['notes']}"
        )
    return (
        "Rewrite the following cultivar records. Use the existing description and notes "
        "as source material but produce fresh, parallel-structure text as specified.\n\n"
        + "\n\n---\n\n".join(parts)
    )


def parse_response(text, expected_names):
    """Parse the Claude response into a dict keyed by cultivar name."""
    results = {}
    # Split on ===CULTIVAR: ...===
    blocks = re.split(r'===CULTIVAR:\s*(.+?)===', text)
    # blocks[0] is before first match, then alternating name, content
    for i in range(1, len(blocks), 2):
        name = blocks[i].strip()
        content = blocks[i + 1] if i + 1 < len(blocks) else ""

        tagline_m = re.search(r'TAGLINE:\s*(.+?)(?=\nDESCRIPTION:|\Z)', content, re.DOTALL)
        desc_m = re.search(r'DESCRIPTION:\s*(.+?)(?=\nNOTES:|\Z)', content, re.DOTALL)
        notes_m = re.search(r'NOTES:\s*(.+)', content, re.DOTALL)

        results[name] = {
            'tagline': tagline_m.group(1).strip() if tagline_m else '',
            'description': desc_m.group(1).strip() if desc_m else '',
            'notes': notes_m.group(1).strip() if notes_m else '',
        }

    return results


def validate_record(name, fields, warn_logger):
    """Validate a single rewritten record. Log warnings."""
    warnings = []

    # Tagline should be one sentence
    tagline = fields.get('tagline', '')
    if tagline.count('.') > 2:
        warnings.append(f"Tagline may contain multiple sentences")

    # Description should be flowing prose (no semicolons as delimiters)
    desc = fields.get('description', '')
    if desc.count(';') > 2:
        warnings.append(f"Description uses semicolons as delimiters")

    # Notes should not open with cultivar name or species
    notes = fields.get('notes', '')
    if notes:
        first_word_block = notes[:60].lower()
        if name.lower().split()[0] in first_word_block.split()[:3]:
            warnings.append(f"Notes opens with cultivar name")
        for species in ['japonica', 'sasanqua', 'reticulata', 'camellia']:
            if first_word_block.startswith(species):
                warnings.append(f"Notes opens with species name '{species}'")

    if not tagline:
        warnings.append("Empty tagline")
    if not desc:
        warnings.append("Empty description")
    if not notes:
        warnings.append("Empty notes")

    for w in warnings:
        warn_logger.warning(f"[{name}] {w}")

    return len(warnings) == 0


def call_api(client, records, dry_run=False):
    """Call Claude API with a batch of records. Returns parsed results."""
    user_prompt = build_user_prompt(records)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — Would send {len(records)} records to API:")
        for r in records:
            print(f"  - {r['cultivar']} (id={r['id']})")
        print(f"{'='*60}")
        print(f"User prompt length: {len(user_prompt)} chars")
        print(f"First 500 chars of prompt:\n{user_prompt[:500]}...")
        return None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            expected = [r['cultivar'] for r in records]
            return parse_response(text, expected)
        except anthropic.APIError as e:
            wait = (2 ** attempt) * 2
            logging.error(f"API error (attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            logging.error(f"Unexpected error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    return None


def match_result_to_record(results, records):
    """Match parsed results back to records, handling minor name differences."""
    matched = {}
    result_names = list(results.keys())

    for rec in records:
        name = rec['cultivar']
        # Exact match first
        if name in results:
            matched[rec['id']] = results[name]
            continue
        # Case-insensitive match
        for rn in result_names:
            if rn.lower() == name.lower():
                matched[rec['id']] = results[rn]
                break
        else:
            # Fuzzy: check if cultivar name is contained
            for rn in result_names:
                if name.lower() in rn.lower() or rn.lower() in name.lower():
                    matched[rec['id']] = results[rn]
                    break

    return matched


def main():
    parser = argparse.ArgumentParser(description="Batch rewrite cultivar fields via Claude API")
    parser.add_argument('--dry-run', action='store_true', help="Preview without making API calls or DB changes")
    parser.add_argument('--limit', type=int, default=0, help="Process only N records (0 = all)")
    parser.add_argument('--start-id', type=int, default=0, help="Start from this cultivar ID")
    parser.add_argument('--api-key', type=str, default='', help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    warn_logger = logging.getLogger('warnings')
    warn_handler = logging.FileHandler(WARNING_LOG, mode='a')
    warn_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    warn_logger.addHandler(warn_handler)

    # API client
    api_key = args.api_key or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key and not args.dry_run:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key) if api_key else None

    # Load records
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Skip records that already have a non-empty tagline (resume support)
    query = """
        SELECT id, cultivar, epithet, category, color_form, description, notes
        FROM cultivar
        WHERE (tagline IS NULL OR tagline = '')
    """
    params = []
    if args.start_id > 0:
        query += " AND id >= ?"
        params.append(args.start_id)

    query += " ORDER BY id"

    if args.limit > 0:
        query += " LIMIT ?"
        params.append(args.limit)

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        print("No records to process (all have taglines already).")
        conn.close()
        return

    print(f"Processing {len(rows)} records in batches of {BATCH_SIZE}...")

    total_processed = 0
    total_warnings = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

        names = [r['cultivar'] for r in batch]
        print(f"\nBatch {batch_num}/{total_batches}: {', '.join(names)}")

        results = call_api(client, batch, dry_run=args.dry_run)

        if args.dry_run:
            total_processed += len(batch)
            continue

        if results is None:
            logging.error(f"Batch {batch_num} failed after retries — skipping")
            continue

        matched = match_result_to_record(results, batch)

        for rec in batch:
            rid = rec['id']
            if rid not in matched:
                logging.error(f"No result matched for '{rec['cultivar']}' (id={rid})")
                continue

            fields = matched[rid]
            is_valid = validate_record(rec['cultivar'], fields, warn_logger)
            if not is_valid:
                total_warnings += 1

            cur.execute(
                "UPDATE cultivar SET tagline = ?, description = ?, notes = ? WHERE id = ?",
                (fields['tagline'], fields['description'], fields['notes'], rid)
            )
            total_processed += 1

        conn.commit()
        logging.info(f"Batch {batch_num} committed ({len(matched)} records)")

        if i + BATCH_SIZE < len(rows):
            time.sleep(DELAY_BETWEEN_CALLS)

    conn.close()

    print(f"\nDone. Processed: {total_processed}, Warnings: {total_warnings}")
    if total_warnings:
        print(f"See {WARNING_LOG} for details.")


if __name__ == '__main__':
    main()
