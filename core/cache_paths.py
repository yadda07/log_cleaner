import logging
import os

logger = logging.getLogger(__name__)

CACHE_DIR_NAME = '__pycache__'

_PRUNED_DIRS = frozenset(('.git', '.hg', '.svn', 'node_modules'))


def resolve_scan_roots(plugin_dir):
    """Racines de scan du profil QGIS courant, déduites du dossier du plugin.

    Le cache bytecode d'un profil ne vit pas uniquement dans ``python/plugins``:
    ``python/expressions``, ``python/`` lui-même et ``processing/`` en contiennent
    aussi.

    Returns:
        tuple: dossiers existants à parcourir, vide si rien d'exploitable.
    """
    plugins_dir = os.path.dirname(plugin_dir)
    python_dir = os.path.dirname(plugins_dir)
    if not _is_profile_layout(plugins_dir, python_dir):
        logger.warning(
            "cache_roots_fallback reason=unexpected_layout plugin_dir=%s",
            plugin_dir
        )
        return (plugins_dir,) if os.path.isdir(plugins_dir) else ()
    profile_dir = os.path.dirname(python_dir)
    candidates = (python_dir, os.path.join(profile_dir, 'processing'))
    roots = tuple(path for path in candidates if os.path.isdir(path))
    logger.debug("cache_roots_resolved n_roots=%s roots=%s", len(roots), roots)
    return roots


def _is_profile_layout(plugins_dir, python_dir):
    """Vérifie le layout attendu <profil>/python/plugins/<plugin>."""
    return (
        os.path.basename(plugins_dir).lower() == 'plugins'
        and os.path.basename(python_dir).lower() == 'python'
    )


def iter_cache_dirs(roots):
    """Énumère les dossiers __pycache__ sous chaque racine.

    Les liens et jonctions de dossiers sont suivis (un plugin de développement
    est souvent monté en jonction), les boucles sont coupées par identité
    device/inode.
    """
    visited = set()
    for root in roots:
        yield from _walk_root(root, visited)


def _walk_root(root, visited):
    """Parcourt une racine et cède chaque __pycache__ rencontré."""
    n_dirs = 0
    for current, dirs, _files in os.walk(root, followlinks=True):
        identity = _dir_identity(current)
        if identity is None or identity in visited:
            dirs[:] = []
            continue
        visited.add(identity)
        n_dirs += 1
        dirs[:] = [name for name in dirs if name not in _PRUNED_DIRS]
        if CACHE_DIR_NAME in dirs:
            dirs.remove(CACHE_DIR_NAME)
            yield os.path.join(current, CACHE_DIR_NAME)
    logger.debug("cache_walk_end root=%s n_dirs=%s", root, n_dirs)


def _dir_identity(path):
    """Identité d'un dossier, utilisée pour couper les boucles de liens."""
    try:
        info = os.stat(path)
    except OSError as exc:
        logger.warning("cache_dir_stat_failed path=%s error=%s", path, exc)
        return None
    if info.st_ino == 0:
        return os.path.normcase(os.path.realpath(path))
    return (info.st_dev, info.st_ino)
