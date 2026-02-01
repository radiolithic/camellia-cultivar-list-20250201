# Gene's Camellias — Cultivar Database

**Live at: https://plants.yd2.studio**

A Flask web application serving an enriched camellia cultivar database as a paginated, editable table. Built to support an ongoing data enrichment workflow that transforms simple cultivar name lists into comprehensive botanical reference records.

## Architecture

```
plants.yd2.studio (Nginx + Certbot SSL)
  → unix:/var/www/genes/genes.sock (Gunicorn, 2 workers)
    → Flask app (SQLite backend)
```

## Features

- **Public read-only table** — paginated view of all cultivars with configurable page size (10/25/50/100)
- **Authenticated inline editing** — password-protected; click any cell in columns 2–7 to edit, auto-saves on blur
- **ICR linking** — cultivar names link to their International Camellia Register pages when a URL is present
- **CSV export** — download the current database as a CSV (authenticated)

## Data Schema

| Column | DB Field | Editable | Description |
|--------|----------|----------|-------------|
| Cultivar | `cultivar` | No | Display name, links to ICR page |
| Epithet | `epithet` | Yes | e.g. `Camellia japonica 'Name'` |
| Category | `category` | Yes | J, S, RH, NRH, Species |
| Color / Form | `color_form` | Yes | e.g. Red / Formal Double |
| Description | `description` | Yes | Size, originator, bloom season |
| Notes | `notes` | Yes | Extended notes, awards, history |
| ICR Link | `image_url` | Yes | URL to ICR or reference page |

## File Structure

```
/var/www/genes/
├── run.py                  # Gunicorn entry point
├── config.py               # Flask configuration
├── import_csv.py           # CSV → SQLite loader
├── enrich.py               # AI enrichment script
├── .env                    # SECRET_KEY, ADMIN_PASSWORD
├── requirements.txt        # Python dependencies
├── genes_combined.csv      # Master input (~555 cultivars)
├── genes_enriched.csv      # Current enriched output (symlink)
├── data/
│   └── genes.db            # SQLite database
└── app/
    ├── __init__.py         # Flask app factory
    ├── models.py           # Cultivar model
    ├── routes.py           # Routes and API
    ├── templates/
    │   ├── base.html       # Layout with header/nav
    │   └── index.html      # Paginated table
    └── static/
        ├── css/style.css
        └── js/main.js      # Inline edit logic
```

## Deployment

Systemd service and Nginx reverse proxy, matching the pattern used by `/var/www/csra`.

**Service:** `/etc/systemd/system/genes.service`
```
sudo systemctl start|stop|restart|status genes
```

**Nginx:** `/etc/nginx/sites-available/plants.yd2.studio`
- SSL managed by Certbot (auto-renew)

## Common Operations

**Reload CSV into database** (after updating `genes_enriched.csv`):
```bash
cd /var/www/genes && python3 import_csv.py
```
This drops and recreates the table — the CSV is the source of truth.

**Restart after code changes:**
```bash
sudo systemctl restart genes
```

**Check logs:**
```bash
sudo journalctl -u genes -f
```

## Authentication

Login via the button in the top-right header. Password is set in `.env` (`ADMIN_PASSWORD`). Once authenticated, table cells become editable and the CSV export link appears.

## API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | No | Paginated table (`?page=1&per_page=25`) |
| POST | `/login` | No | Form post with `password` field |
| POST | `/logout` | No | Clears session |
| PUT | `/api/cultivar/<id>` | Yes | Update fields (JSON body) |
| GET | `/api/export` | Yes | Download CSV |
