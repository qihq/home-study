import os
import subprocess
import sys
from pathlib import Path


def test_alembic_configuration_has_an_initial_revision() -> None:
    root = Path(__file__).parents[1]
    assert (root / 'alembic.ini').is_file()
    revisions = list((root / 'alembic' / 'versions').glob('*.py'))
    assert (root / 'alembic' / 'versions' / '0001_initial.py') in revisions
    assert revisions


def test_fresh_database_upgrades_to_head(tmp_path: Path) -> None:
    database = tmp_path / 'fresh.db'
    environment = {
        **os.environ,
        'APP_DATA_DIR': str(tmp_path / 'data'),
        'APP_DATABASE_URL': f'sqlite:///{database}',
    }

    subprocess.run(
        [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
        cwd=Path(__file__).parents[1], env=environment, check=True,
    )
