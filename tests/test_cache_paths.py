from core.cache_paths import iter_cache_dirs, resolve_scan_roots


def test_roots_cover_python_and_processing(profile):
    (profile.python_dir / 'expressions').mkdir()

    roots = resolve_scan_roots(str(profile.plugin_dir))

    assert roots == (str(profile.python_dir), str(profile.processing_dir))


def test_roots_ignore_missing_processing(profile):
    profile.processing_dir.rmdir()

    roots = resolve_scan_roots(str(profile.plugin_dir))

    assert roots == (str(profile.python_dir),)


def test_roots_fallback_when_layout_unexpected(tmp_path):
    plugin_dir = tmp_path / 'somewhere' / 'log_cleaner'
    plugin_dir.mkdir(parents=True)

    roots = resolve_scan_roots(str(plugin_dir))

    assert roots == (str(tmp_path / 'somewhere'),)


def test_roots_empty_when_nothing_exists(tmp_path):
    ghost = tmp_path / 'ghost' / 'log_cleaner'

    assert resolve_scan_roots(str(ghost)) == ()


def test_iter_finds_nested_and_root_caches(profile, add_cache):
    expected = {
        str(add_cache(profile.python_dir, 'startup.cpython-312.pyc')),
        str(add_cache(profile.python_dir / 'expressions', 'e.cpython-312.pyc')),
        str(add_cache(profile.plugins_dir / 'other' / 'core', 'm.cpython-312.pyc')),
        str(add_cache(profile.processing_dir / 'scripts', 's.cpython-312.pyc')),
    }

    found = set(iter_cache_dirs(resolve_scan_roots(str(profile.plugin_dir))))

    assert found == expected


def test_iter_prunes_vcs_directories(profile, add_cache):
    add_cache(profile.plugins_dir / 'other' / '.git' / 'hooks', 'h.cpython-312.pyc')

    found = list(iter_cache_dirs(resolve_scan_roots(str(profile.plugin_dir))))

    assert found == []


def test_iter_does_not_descend_into_cache_dir(profile, add_cache):
    cache_dir = add_cache(profile.plugins_dir / 'other', 'm.cpython-312.pyc')
    (cache_dir / '__pycache__').mkdir()

    found = list(iter_cache_dirs(resolve_scan_roots(str(profile.plugin_dir))))

    assert found == [str(cache_dir)]


def test_iter_follows_junction(profile, add_cache, make_junction, tmp_path):
    external = tmp_path / 'dev_repo'
    cache_dir = add_cache(external, 'm.cpython-312.pyc')
    make_junction(profile.plugins_dir / 'linked_plugin', external)

    found = list(iter_cache_dirs(resolve_scan_roots(str(profile.plugin_dir))))

    assert len(found) == 1
    assert found[0].endswith('linked_plugin\\__pycache__')
    assert cache_dir.exists()


def test_iter_breaks_junction_loop(profile, add_cache, make_junction):
    add_cache(profile.python_dir / 'expressions', 'e.cpython-312.pyc')
    make_junction(profile.plugins_dir / 'loop', profile.python_dir)

    found = list(iter_cache_dirs(resolve_scan_roots(str(profile.plugin_dir))))

    assert len(found) == 1


def test_iter_reports_same_dir_once_across_roots(profile, add_cache):
    cache_dir = add_cache(profile.processing_dir / 'scripts', 's.cpython-312.pyc')
    roots = (str(profile.processing_dir), str(profile.processing_dir))

    found = list(iter_cache_dirs(roots))

    assert found == [str(cache_dir)]
