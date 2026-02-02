# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gene's Camellias is a Flask web application for browsing and curating a database of ~555 camellia cultivars, with an AI-powered data enrichment pipeline. Live at **https://plants.yd2.studio**.

Two main components:
1. **Web app** — Flask + SQLite, public browsable table with authenticated inline editing
2. **Enrichment scripts** — Python scripts using the Anthropic Claude API and web scraping to populate cultivar data

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Import CSV into SQLite (drops and recreates the table)
python3 import_csv.py

# Run enrichment pipeline (Claude API + iflora scraping)
python3 enrich.py --limit 10

# Rewrite fields via Claude API (preview first with --dry-run)
python3 rewrite_fields.py --dry-run

# Scrape photo URLs from iflora.cn
python3 scrape_photos.py

# Restart the production service
sudo systemctl restart genescamelliaworld

# Quick redeploy (pulls latest code and restarts)
./deploy/redeploy.sh

# View production logs
sudo journalctl -u genescamelliaworld -f
```

## Architecture

```
Nginx (Cloudflare Origin CA SSL)
  → Gunicorn (2 workers, Unix socket)
    → Flask app (app/__init__.py factory)
      → SQLite (data/genes.db)
```

- **`app/__init__.py`** — App factory, database initialization
- **`app/models.py`** — `Cultivar` model (main table) and `CultivarHistory` (audit log tracking per-field edits)
- **`app/routes.py`** — All routes and API endpoints
- **`app/templates/`** — Jinja2 templates: `base.html` (layout), `index.html` (full table), `list.html` (compact multi-column), `edit.html` (single-record form with Quill.js rich text editor)
- **`app/static/`** — `css/style.css` and `js/main.js` (inline editing, zoom controls)
- **`config.py`** — Flask config loading from `.env`
- **`run.py`** — Gunicorn entry point (`run:app`)

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | No | Redirects to `/list` |
| GET | `/table` | No | Paginated table (`?page=&per_page=&q=`) |
| GET | `/list` | No | Multi-column list view |
| GET | `/edit/<id>` | Yes | Single-record edit form |
| PUT | `/api/cultivar/<id>` | Yes | Update fields (JSON body) |
| GET | `/api/cultivar/<id>/history` | Yes | Field edit history |
| GET | `/api/export` | Yes | CSV download |

## Data Model

The `cultivar` table has: `id`, `cultivar`, `epithet`, `category`, `color_form`, `tagline`, `description`, `notes` (may contain HTML from Quill), `image_url` (ICR page link), `photo_url`, `validated` (boolean), `priority` (boolean).

The `cultivar_history` table tracks all edits with `field_name`, `old_value`, `new_value`, `timestamp`.

## Category Codes

| Code | Species |
|------|---------|
| J | *Camellia japonica* |
| S | *Camellia sasanqua* |
| RH | Reticulata Hybrid |
| NRH | Non-Reticulata Hybrid |
| Species | Wild/species types |

## Enrichment Data Conventions

- Epithet format: `Camellia japonica 'Cultivar Name'`
- **Flower forms:** Single, Semi-double, Anemone, Peony, Rose-form Double, Formal Double
- **Flower sizes:** Miniature (<2"), Small (2-3"), Medium (3-4"), Large (4-5"), Very Large (>5")
- **Standard colors:** White, Blush, Pink, Rose, Red, Coral, Variegated
- Descriptions prioritize: flower size, originator/location/year, parentage (hybrids), bloom season, growth habit, awards
- Unknown cultivars: mark as "Unknown - possibly unregistered or misspelled"
- Priority research sources: camellia.iflora.cn, americancamellias.com, specialty nurseries, university extensions

## Configuration

Environment variables in `.env` (not tracked):
- `SECRET_KEY` — Flask session signing
- `ADMIN_PASSWORD` — Single admin password
- `DATABASE_URL` — SQLAlchemy URI (default: `sqlite:///data/genes.db`)

Deployment config in `deploy/deploy.conf` (not tracked, see `deploy.conf.example`).

## Key Details

- **After any substantial code edit, restart the production service** with `sudo systemctl restart genescamelliaworld` so changes take effect
- Authentication is a simple session-based password login (no user accounts)
- Database backups are created automatically on admin login (`app/backup.py`)
- All enrichment scripts support resume and are idempotent
- `import_csv.py` drops and recreates the table — the CSV is the source of truth when used
- The `notes` field may contain HTML from the Quill rich text editor
- Frontend uses no build step — plain CSS/JS with Quill.js loaded from CDN
