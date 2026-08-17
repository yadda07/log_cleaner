import os
import stat
import sys

import pytest

from core.cache_cleaner import PluginCacheCleaner


def _clean(profile):
    return PluginCacheCleaner(str(profile.plugin_dir)).clean()


def test_every_profile_root_is_cleaned(profile, add_cache):
    caches = [
        add_cache(profile.python_dir, 'startup.cpython-312.pyc'),
        add_cache(profile.python_dir / 'expressions', 'e.cpython-312.pyc'),
        add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc'),
        add_cache(profile.processing_dir / 'scripts', 's.cpython-312.pyc'),
    ]

    result = _clean(profile)

    assert [cache.exists() for cache in caches] == [False, False, False, False]
    assert result.success is True
    assert result.removed == 4
    assert result.errors == 0
    assert result.message == 'Cache: 4 files, 4 dirs'


def test_own_cache_is_cleaned(profile, add_cache):
    own = add_cache(profile.plugin_dir / 'core', 'cache_cleaner.cpython-312.pyc')

    result = _clean(profile)

    assert not own.exists()
    assert result.removed == 1
    assert len(result.paths_succeeded) == 1


def test_foreign_file_keeps_dir_and_is_reported(profile, add_cache):
    cache = add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc', 'notes.txt')

    result = _clean(profile)

    assert not (cache / 'm.cpython-312.pyc').exists()
    assert (cache / 'notes.txt').exists()
    assert result.paths_failed == (str(cache),)
    assert result.errors == 0
    assert result.success is True
    assert result.message == 'Cache: 1 files, 0 dirs, 1 kept (see Log Messages)'


def test_subdirectory_keeps_dir_and_is_reported(profile, add_cache):
    cache = add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc')
    (cache / 'nested').mkdir()

    result = _clean(profile)

    assert cache.exists()
    assert result.paths_failed == (str(cache),)
    assert result.message.endswith('1 kept (see Log Messages)')


def test_readonly_bytecode_is_deleted(profile, add_cache):
    cache = add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc')
    target = cache / 'm.cpython-312.pyc'
    os.chmod(target, stat.S_IREAD)

    result = _clean(profile)

    assert not target.exists()
    assert not cache.exists()
    assert result.success is True
    assert result.errors == 0


def test_atomic_write_leftover_is_deleted(profile, add_cache):
    cache = add_cache(
        profile.plugins_dir / 'other',
        'm.cpython-312.pyc.4172',
        'm.cpython-312.opt-1.pyc',
        'legacy.pyo',
    )

    result = _clean(profile)

    assert not cache.exists()
    assert result.removed == 1
    assert result.message == 'Cache: 3 files, 1 dirs'


def test_bytecode_outside_cache_dir_is_untouched(profile, add_cache):
    package = profile.plugins_dir / 'other'
    add_cache(package, 'm.cpython-312.pyc')
    legacy = package / 'sourceless.pyc'
    legacy.write_bytes(b'\x00' * 8)

    result = _clean(profile)

    assert legacy.exists()
    assert result.removed == 1


def test_nothing_to_clean_is_explicit(profile):
    result = _clean(profile)

    assert result.success is True
    assert result.removed == 0
    assert result.message == 'Cache: nothing to clean'


def test_missing_scan_root_fails_loudly(tmp_path):
    ghost = tmp_path / 'ghost' / 'log_cleaner'

    result = PluginCacheCleaner(str(ghost)).clean()

    assert result.success is False
    assert 'no scan root found' in result.message


def test_reported_paths_are_bounded(profile, add_cache):
    for index in range(25):
        add_cache(profile.plugins_dir / ('plug%s' % index), 'notes.txt')

    result = _clean(profile)

    assert len(result.paths_failed) == 20
    assert result.message == 'Cache: 0 files, 0 dirs, 25 kept (see Log Messages)'


def test_succeeded_paths_are_bounded(profile, add_cache):
    for index in range(25):
        add_cache(profile.plugins_dir / ('plug%s' % index), 'm.cpython-312.pyc')

    result = _clean(profile)

    assert len(result.paths_succeeded) == 20
    assert result.removed == 25


@pytest.mark.skipif(sys.platform != 'win32', reason='verrou exclusif Windows')
def test_locked_bytecode_is_reported_as_error(profile, add_cache):
    cache = add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc')
    target = cache / 'm.cpython-312.pyc'

    with open(target, 'rb'):
        result = _clean(profile)

    assert target.exists()
    assert result.success is False
    assert result.errors == 1
    assert result.paths_failed == (str(cache),)
    assert result.message == 'Cache: 0 files, 0 dirs, 1 locked (see Log Messages)'


def test_symlinked_cache_dir_is_kept_and_reported(profile, add_cache, tmp_path):
    external = add_cache(tmp_path / 'external', 'm.cpython-312.pyc')
    package = profile.plugins_dir / 'other'
    package.mkdir(parents=True)
    link = package / '__pycache__'
    try:
        os.symlink(external, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip('symlink non autorisé: %s' % exc)

    result = _clean(profile)

    assert (external / 'm.cpython-312.pyc').exists()
    assert result.paths_failed == (str(link),)
    assert result.errors == 0


def test_junction_target_cache_is_cleaned(profile, add_cache, make_junction, tmp_path):
    external = tmp_path / 'dev_repo'
    cache = add_cache(external, 'm.cpython-312.pyc')
    make_junction(profile.plugins_dir / 'linked_plugin', external)

    result = _clean(profile)

    assert not cache.exists()
    assert result.removed == 1
    assert result.success is True
