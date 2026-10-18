import logging
import os

logger = logging.getLogger(__name__)

CACHE_DIR_NAME = '__pycache__'

_PRUNED_DIRS = frozenset((
    '.git', '.hg', '.svn', 'node_modules',
    'venv', 'env', 'site-packages', 'wheels',
    'build', 'dist', 'outputs', 'livrables', 'htmlcov',
))


def _is_pruned_dir(name):
    """Indique si un sous-dossier doit être exclu du parcours."""
    return name.startswith('.') or name in _PRUNED_DIRS


def resolve_scan_roots(plugin_dir, extra_roots=()):
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
        base = (plugins_dir,) if os.path.isdir(plugins_dir) else ()
        return _merge_extra_roots(base, extra_roots)
    profile_dir = os.path.dirname(python_dir)
    candidates = (python_dir, os.path.join(profile_dir, 'processing'))
    roots = _merge_extra_roots(
        tuple(path for path in candidates if os.path.isdir(path)),
        extra_roots
    )
    logger.debug("cache_roots_resolved n_roots=%s roots=%s", len(roots), roots)
    return roots


def _merge_extra_roots(base_roots, extra_roots):
    """Ajoute les racines supplémentaires existantes sans doublon."""
    if not extra_roots:
        return base_roots
    merged = list(base_roots)
    seen = {os.path.normcase(os.path.abspath(p)) for p in base_roots}
    for path in extra_roots:
        if not path or not os.path.isdir(path):
            continue
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen:
            seen.add(norm)
            merged.append(path)
    return tuple(merged)


def _is_profile_layout(plugins_dir, python_dir):
    """Vérifie le layout attendu <profil>/python/plugins/<plugin>."""
    return (
        os.path.basename(plugins_dir).lower() == 'plugins'
        and os.path.basename(python_dir).lower() == 'python'
    )


def iter_cache_dirs(roots, cancel_event=None):
    """Énumère les dossiers __pycache__ sous chaque racine.

    Les liens et jonctions de dossiers sont suivis (un plugin de développement
    est souvent monté en jonction), les boucles sont coupées par identité
    device/inode.
    """
    visited = set()
    for root in roots:
        if cancel_event is not None and cancel_event.is_set():
            logger.debug("cache_walk_cancelled root=%s", root)
            return
        yield from _walk_root(root, visited, cancel_event)


def _walk_root(root, visited, cancel_event=None):
    """Parcourt une racine et cède chaque __pycache__ rencontré."""
    n_dirs = 0
    for current, dirs, _files in os.walk(root, followlinks=True):
        if cancel_event is not None and cancel_event.is_set():
            dirs[:] = []
            return
        identity = _dir_identity(current)
        if identity is None or identity in visited:
            dirs[:] = []
            continue
        visited.add(identity)
        n_dirs += 1
        if CACHE_DIR_NAME in dirs:
            dirs.remove(CACHE_DIR_NAME)
            yield os.path.join(current, CACHE_DIR_NAME)
        dirs[:] = [name for name in dirs if not _is_pruned_dir(name)]
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
