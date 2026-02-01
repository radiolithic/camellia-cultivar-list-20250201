# Gene's Camellias — Application Documentation

## 1. Functional Overview

Gene's Camellias is a web application for browsing and curating a database of ~555 camellia cultivars. It serves two audiences: public visitors who can browse the collection, and an authenticated administrator who can edit records and export data.

### Public Features

- **Full Table View** (`/`) — Paginated, searchable table showing all cultivar fields: name, botanical epithet, species category, color/form, tagline, description, notes, and photos. Configurable rows per page (10/25/50/100).
- **List View** (`/list`) — Compact multi-column layout of cultivar names, auto-sized to the browser viewport. Clicking a name searches for it in the full table. Includes a zoom control (50%–200%) persisted in the browser session.
- **Search** — Filter cultivars by name from either view. Searches from the list view redirect to the full table.

### Authenticated Features

- **Inline Editing** — In the full table, all text fields become contenteditable. Changes auto-save on blur via the REST API.
- **Single-Record Edit Form** (`/edit/<id>`) — Dedicated page for editing one cultivar at a time with standard form inputs, a Quill rich-text editor for the Notes field, and prev/next navigation.
- **CSV Export** (`/api/export`) — Download the full database as a CSV file.

### Authentication

Simple session-based password login. A single admin password is configured via environment variable. Failed logins display an error message.

---

## 2. Architecture

### Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3 |
| Framework | Flask 3.x with Blueprints |
| ORM | Flask-SQLAlchemy |
| Database | SQLite (file-based) |
| WSGI Server | Gunicorn (2 workers, Unix socket) |
| Reverse Proxy | Nginx with SSL (Let's Encrypt) |
| Rich Text | Quill.js 1.3.7 (CDN) |
| AI Enrichment | Anthropic Claude API |

### Deployment Topology

```
Browser
  │
  ▼ HTTPS (port 443)
Nginx (plants.yd2.studio)
  │
  ▼ Unix socket (/var/www/genes/genes.sock)
Gunicorn (2 workers)
  │
  ▼
Flask App
  │
  ▼
SQLite (/var/www/genes/data/genes.db)
```

Nginx handles SSL termination, static file serving (30-day cache), and proxies dynamic requests to Gunicorn. A systemd service (`genes.service`) manages the Gunicorn process with auto-restart.

### Directory Structure

```
/var/www/genes/
├── app/
│   ├── __init__.py          # App factory, DB init
│   ├── models.py            # Cultivar model
│   ├── routes.py            # Routes and API
│   ├── templates/
│   │   ├── base.html        # Shared layout
│   │   ├── index.html       # Full table view
│   │   ├── list.html        # Multi-column list view
│   │   └── edit.html        # Single-record edit form
│   └── static/
│       ├── css/style.css    # All styles
│       └── js/main.js       # Inline editing, UI logic
├── config.py                # Flask config (DB path, secrets)
├── run.py                   # Entry point (Gunicorn imports run:app)
├── import_csv.py            # Load CSV into database
├── enrich.py                # AI enrichment pipeline
├── rewrite_fields.py        # AI field rewriting
├── scrape_photos.py         # Photo URL scraper
├── data/genes.db            # SQLite database
├── genes_combined.csv       # Master cultivar list (input)
├── genes_upload.csv         # Enriched CSV (output)
├── requirements.txt         # Python dependencies
└── .env                     # SECRET_KEY, ADMIN_PASSWORD
```

---

## 3. Technical Reference

### Data Model

Single table: `cultivar`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment identifier |
| `cultivar` | String(200) | Display name (e.g., "Kramer's Supreme") |
| `epithet` | String(300) | Botanical name (e.g., "Camellia japonica 'Kramer's Supreme'") |
| `category` | String(20) | Species code: J, S, RH, NRH, or Species |
| `color_form` | String(200) | Color and flower form (e.g., "Red / Peony") |
| `tagline` | Text | One-sentence summary |
| `description` | Text | Compact factual description |
| `notes` | Text | Narrative notes (may contain HTML from Quill editor) |
| `image_url` | String(500) | Link to ICR (iflora.cn) page |
| `photo_url` | String(500) | Direct photo URL |

### Routes

| Path | Method | Auth | Description |
|------|--------|------|-------------|
| `/` | GET | No | Full table view (params: `page`, `per_page`, `q`) |
| `/list` | GET | No | Multi-column list view |
| `/edit/<id>` | GET | Yes | Single-record edit form |
| `/login` | POST | No | Authenticate (form field: `password`) |
| `/logout` | POST | No | Clear session |
| `/api/cultivar/<id>` | PUT | Yes | Update cultivar fields (JSON body) |
| `/api/export` | GET | Yes | Download full CSV |

### API: PUT /api/cultivar/<id>

**Request:** JSON object with any subset of editable fields:
```json
{
  "epithet": "...",
  "category": "...",
  "color_form": "...",
  "tagline": "...",
  "description": "...",
  "notes": "...",
  "image_url": "...",
  "photo_url": "..."
}
```

**Response:** Full cultivar object as JSON. Returns 401 if not authenticated.

### Offline Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `import_csv.py` | Reset database from CSV | `python import_csv.py` |
| `enrich.py` | Enrich cultivars via Claude API + iflora scraping | `python enrich.py --limit 10` |
| `rewrite_fields.py` | Rewrite tagline/description/notes via Claude API | `python rewrite_fields.py --dry-run` |
| `scrape_photos.py` | Extract photo URLs from iflora.cn pages | `python scrape_photos.py` |

All enrichment scripts support resume (track last processed record) and are idempotent.

### Configuration

Environment variables (loaded from `.env`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Flask session signing | `dev-secret-key-change-in-production` |
| `ADMIN_PASSWORD` | Login password | `genesautumnfire1` |
| `DATABASE_URL` | SQLAlchemy URI | `sqlite:///data/genes.db` |

### Dependencies

Flask, Flask-SQLAlchemy, Gunicorn, python-dotenv, anthropic (Claude SDK), requests, beautifulsoup4.

### Operations

```bash
# Restart after code changes
sudo systemctl restart genes

# Check status
sudo systemctl status genes

# View logs
sudo journalctl -u genes -f

# Database is at
/var/www/genes/data/genes.db
```
