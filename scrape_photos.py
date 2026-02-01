#!/usr/bin/env python3
"""Scrape photo URLs from iflora.cn ICR pages for cultivars that have an ICR link."""
import re
import time
import sqlite3
import requests

DB_PATH = 'data/genes.db'
IFLORA_IP = '210.72.88.216'

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (compatible; CamelliaDB/1.0)',
})

def resolve_iflora(url):
    """Fetch iflora URL using direct IP to bypass DNS issues."""
    # Replace hostname with IP in the actual connection but keep Host header
    ip_url = url.replace('camellia.iflora.cn', IFLORA_IP)
    return session.get(ip_url, headers={'Host': 'camellia.iflora.cn'},
                       timeout=15, verify=False)

def extract_photo_url(html):
    """Extract the DefaultPhoto image src from the page HTML."""
    match = re.search(r'id="DefaultPhoto"\s+src="([^"]+)"', html)
    if match:
        return match.group(1)
    return ''

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, cultivar, image_url FROM cultivar
        WHERE image_url LIKE '%iflora.cn%'
        AND (photo_url IS NULL OR photo_url = '')
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f'Found {total} cultivars to scrape.')

    success = 0
    failed = 0
    for i, (cid, name, icr_url) in enumerate(rows, 1):
        try:
            resp = resolve_iflora(icr_url)
            photo = extract_photo_url(resp.text)
            if photo:
                cur.execute('UPDATE cultivar SET photo_url = ? WHERE id = ?', (photo, cid))
                conn.commit()
                success += 1
                print(f'[{i}/{total}] {name}: {photo}')
            else:
                print(f'[{i}/{total}] {name}: no photo found')
                failed += 1
        except Exception as e:
            print(f'[{i}/{total}] {name}: ERROR {e}')
            failed += 1

        # Be polite — 1 second between requests
        if i < total:
            time.sleep(1)

    print(f'\nDone. {success} photos saved, {failed} without photos.')
    conn.close()

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
