#!/usr/bin/env python3
"""Import genes_enriched.csv into SQLite database."""
import csv
from app import create_app, db
from app.models import Cultivar

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    with open('genes_enriched.csv', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = Cultivar(
                cultivar=row.get('Cultivar', '').strip(),
                epithet=row.get('Epithet', '').strip(),
                category=row.get('Category', '').strip(),
                color_form=row.get('Color / Form', '').strip(),
                description=row.get('Description', '').strip(),
                notes=row.get('Notes', '').strip(),
                image_url=row.get('Image URL', '').strip(),
            )
            db.session.add(c)

    db.session.commit()
    count = Cultivar.query.count()
    print(f'Imported {count} cultivars.')
