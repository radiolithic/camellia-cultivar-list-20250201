import os
import shutil
from datetime import datetime
from pathlib import Path


def backup_database(db_path, keep=10):
    """Copy the SQLite database to a timestamped backup file, pruning old backups."""
    db_path = Path(db_path)
    if not db_path.exists():
        return

    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_dir / f'genes_{timestamp}.db'
    shutil.copy2(db_path, backup_file)

    # Prune old backups, keeping only the most recent `keep`
    backups = sorted(backup_dir.glob('genes_*.db'))
    for old in backups[:-keep]:
        old.unlink()
