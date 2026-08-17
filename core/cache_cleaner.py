import logging
import os
import re
import stat
import time
from dataclasses import dataclass, field

from .base_cleaner import Cleaner, CleanResult
from .cache_paths import iter_cache_dirs, resolve_scan_roots

logger = logging.getLogger(__name__)

# Bytecode et résidus d'écriture atomique de CPython (module.pyc.<pid>).
_CACHE_NAME_RE = re.compile(r"\.py[co](\.\d+|\.tmp)?$", re.IGNORECASE)
_MAX_REPORTED_PATHS = 20
_MAX_LOGGED_SAMPLES = 3


@dataclass
class _DirOutcome:
    """Bilan d'un dossier __pycache__ traité."""

    removed: int = 0
    failed: int = 0
    kept: int = 0


@dataclass
class _Report:
    """Bilan agrégé d'une passe de nettoyage."""

    found: int = 0
    removed_files: int = 0
    removed_dirs: int = 0
    kept_dirs: int = 0
    failed_dirs: int = 0
    paths_failed: list = field(default_factory=list)
    paths_succeeded: list = field(default_factory=list)


def _append_bounded(paths, value):
    """Ajoute un chemin au rapport en bornant la taille de la liste."""
    if len(paths) < _MAX_REPORTED_PATHS:
        paths.append(value)


def _entry_block_reason(entry):
    """Raison de conservation d'une entrée, None si elle doit être supprimée."""
    try:
        if entry.is_symlink():
            return 'symlink'
        if not entry.is_file():
            return 'not_a_file'
    except OSError as exc:
        return 'stat_failed:%s' % type(exc).__name__
    if not _CACHE_NAME_RE.search(entry.name):
        return 'not_bytecode'
    return None


def _delete_file(path):
    """Supprime un fichier de cache, avec reprise sur attribut lecture seule."""
    try:
        os.remove(path)
        return True
    except PermissionError as exc:
        logger.debug("cache_file_permission_retry path=%s error=%s", path, exc)
    except OSError as exc:
        logger.warning("cache_file_remove_failed path=%s error=%s", path, exc)
        return False
    return _delete_readonly_file(path)


def _delete_readonly_file(path):
    """Retire l'attribut lecture seule puis retente la suppression."""
    try:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)
    except OSError as exc:
        logger.warning("cache_file_locked path=%s error=%s", path, exc)
        return False
    logger.debug("cache_file_removed_after_chmod path=%s", path)
    return True


def _purge_cache_dir(cache_path, succeeded):
    """Supprime le bytecode d'un __pycache__ et retourne son bilan."""
    try:
        entries = os.scandir(cache_path)
    except OSError as exc:
        logger.warning(
            "cache_scandir_failed cache_path=%s error=%s", cache_path, exc
        )
        return _DirOutcome(failed=1)
    outcome = _DirOutcome()
    sample = []
    with entries:
        for entry in entries:
            reason = _entry_block_reason(entry)
            if reason is not None:
                outcome.kept += 1
                if len(sample) < _MAX_LOGGED_SAMPLES:
                    sample.append('%s:%s' % (entry.name, reason))
                continue
            if _delete_file(entry.path):
                outcome.removed += 1
                _append_bounded(succeeded, entry.path)
            else:
                outcome.failed += 1
    if outcome.kept:
        logger.warning(
            "cache_entries_kept cache_path=%s n_items=%s sample=%s",
            cache_path, outcome.kept, ', '.join(sample)
        )
    return outcome


def _remove_empty_dir(cache_path):
    """Supprime le dossier de cache devenu vide."""
    try:
        os.rmdir(cache_path)
    except OSError as exc:
        logger.warning(
            "cache_rmdir_failed cache_path=%s error=%s", cache_path, exc
        )
        return False
    logger.debug("cache_dir_removed cache_path=%s", cache_path)
    return True


def _purge_one_dir(cache_path, report):
    """Traite un __pycache__ et met à jour le rapport agrégé."""
    if os.path.islink(cache_path):
        logger.warning(
            "cache_dir_kept cache_path=%s reason=symlink_dir", cache_path
        )
        report.kept_dirs += 1
        _append_bounded(report.paths_failed, cache_path)
        return
    outcome = _purge_cache_dir(cache_path, report.paths_succeeded)
    report.removed_files += outcome.removed
    if outcome.failed == 0 and outcome.kept == 0:
        if _remove_empty_dir(cache_path):
            report.removed_dirs += 1
            return
        report.failed_dirs += 1
    elif outcome.failed:
        report.failed_dirs += 1
    else:
        report.kept_dirs += 1
    _append_bounded(report.paths_failed, cache_path)


def _build_message(report):
    """Message court affiché dans la barre d'état."""
    if report.found == 0:
        return "Cache: nothing to clean"
    parts = [
        '%s files' % report.removed_files,
        '%s dirs' % report.removed_dirs,
    ]
    if report.failed_dirs:
        parts.append('%s locked' % report.failed_dirs)
    if report.kept_dirs:
        parts.append('%s kept' % report.kept_dirs)
    message = 'Cache: ' + ', '.join(parts)
    if report.failed_dirs or report.kept_dirs:
        message += ' (see Log Messages)'
    return message


class PluginCacheCleaner(Cleaner):
    """Nettoyeur du bytecode Python du profil QGIS courant."""

    @property
    def label(self):
        return "Cache"

    @property
    def tooltip(self):
        return "Clear compiled Python cache of the current profile"

    @property
    def icon_type(self):
        return "broom"

    @property
    def thread_safe(self):
        return True

    def __init__(self, plugin_path=None):
        if plugin_path is None:
            plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._plugin_dir = plugin_path

    def clean(self):
        t0 = time.perf_counter()
        roots = resolve_scan_roots(self._plugin_dir)
        logger.debug(
            "cache_clean_start plugin_dir=%s n_roots=%s",
            self._plugin_dir, len(roots)
        )
        if not roots:
            return self._failure(
                "Cache: no scan root found for %s" % self._plugin_dir, t0
            )
        return self._build_result(self._purge_roots(roots), t0)

    @staticmethod
    def _purge_roots(roots):
        """Traite tous les __pycache__ des racines et agrège le rapport."""
        report = _Report()
        for cache_path in iter_cache_dirs(roots):
            report.found += 1
            _purge_one_dir(cache_path, report)
        return report

    @staticmethod
    def _build_result(report, t0):
        """Construit le CleanResult final et journalise le bilan."""
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.debug(
            "cache_clean_end found=%s removed_files=%s removed_dirs=%s "
            "kept_dirs=%s failed_dirs=%s elapsed_ms=%.2f",
            report.found, report.removed_files, report.removed_dirs,
            report.kept_dirs, report.failed_dirs, elapsed_ms
        )
        return CleanResult(
            success=report.failed_dirs == 0,
            removed=report.removed_dirs,
            errors=report.failed_dirs,
            paths_failed=tuple(report.paths_failed),
            paths_succeeded=tuple(report.paths_succeeded),
            elapsed_ms=elapsed_ms,
            message=_build_message(report)
        )

    @staticmethod
    def _failure(message, t0):
        """Rapport d'échec immédiat, jamais silencieux."""
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.warning(
            "cache_clean_failed reason=%s elapsed_ms=%.2f", message, elapsed_ms
        )
        return CleanResult(success=False, message=message, elapsed_ms=elapsed_ms)
