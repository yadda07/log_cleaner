import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))


class FakeProfile:
    """Arborescence minimale d'un profil QGIS pour les tests."""

    def __init__(self, root):
        self.root = root
        self.profile_dir = root / 'profiles' / 'default'
        self.python_dir = self.profile_dir / 'python'
        self.plugins_dir = self.python_dir / 'plugins'
        self.plugin_dir = self.plugins_dir / 'log_cleaner'
        self.processing_dir = self.profile_dir / 'processing'
        self.plugin_dir.mkdir(parents=True)
        self.processing_dir.mkdir(parents=True)


@pytest.fixture
def profile(tmp_path):
    return FakeProfile(tmp_path)


@pytest.fixture
def add_cache():
    """Crée <directory>/__pycache__ contenant les fichiers demandés."""

    def _add_cache(directory, *names):
        cache_dir = Path(directory) / '__pycache__'
        cache_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (cache_dir / name).write_bytes(b'\x00' * 8)
        return cache_dir

    return _add_cache


@pytest.fixture
def make_junction():
    """Crée une jonction Windows, saute le test si impossible."""

    def _make_junction(link, target):
        if sys.platform != 'win32':
            pytest.skip('jonction spécifique Windows')
        completed = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
            capture_output=True, text=True, timeout=30
        )
        if completed.returncode != 0:
            pytest.skip('mklink indisponible: %s' % completed.stdout.strip())
        return Path(link)

    return _make_junction
