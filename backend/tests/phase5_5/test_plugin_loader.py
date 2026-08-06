"""
test_plugin_loader.py -- Task 5.5.4 validation
Tests for app/core/plugins/loader.py
"""
from __future__ import annotations

import pytest
from app.core.plugins import PluginLoader, PluginLoadError


# ── Fixtures: real importable classes ────────────────────────
# We use stdlib classes as real targets -- no mocking needed.

_VALID_PATH    = "collections.OrderedDict"
_VALID_PATH_2  = "collections.defaultdict"
_BAD_MODULE    = "nonexistent_module_xyz.SomeClass"
_BAD_ATTR      = "collections.NonExistentClass"
_NOT_A_CLASS   = "os.path.sep"          # a string, not a class
_NO_DOT        = "justaplainname"


# ── Basic loading ─────────────────────────────────────────────

class TestLoad:

    def test_load_valid_class(self):
        loader = PluginLoader()
        cls = loader.load(_VALID_PATH)
        from collections import OrderedDict
        assert cls is OrderedDict

    def test_load_returns_type(self):
        loader = PluginLoader()
        cls = loader.load(_VALID_PATH)
        assert isinstance(cls, type)

    def test_load_bad_module_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Cannot import module"):
            loader.load(_BAD_MODULE)

    def test_load_bad_attribute_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="has no attribute"):
            loader.load(_BAD_ATTR)

    def test_load_not_a_class_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="not a class"):
            loader.load(_NOT_A_CLASS)

    def test_load_no_dot_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Invalid plugin_class"):
            loader.load(_NO_DOT)

    def test_load_empty_string_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="must not be empty"):
            loader.load("")

    def test_load_whitespace_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="must not be empty"):
            loader.load("   ")


# ── Interface validation ──────────────────────────────────────

class TestInterfaceValidation:

    def test_load_with_valid_base(self):
        loader = PluginLoader()
        # OrderedDict is a subclass of dict
        cls = loader.load(_VALID_PATH, expected_base=dict)
        from collections import OrderedDict
        assert cls is OrderedDict

    def test_load_with_invalid_base_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="does not implement"):
            loader.load(_VALID_PATH, expected_base=list)

    def test_load_exact_base_accepted(self):
        loader = PluginLoader()
        # dict is a subclass of object
        cls = loader.load(_VALID_PATH, expected_base=object)
        assert cls is not None


# ── Import cache ──────────────────────────────────────────────

class TestImportCache:

    def test_same_class_returned_from_cache(self):
        loader = PluginLoader()
        cls1 = loader.load(_VALID_PATH)
        cls2 = loader.load(_VALID_PATH)
        assert cls1 is cls2

    def test_cached_paths_empty_initially(self):
        loader = PluginLoader()
        assert loader.cached_paths() == []

    def test_cached_paths_populated_after_load(self):
        loader = PluginLoader()
        loader.load(_VALID_PATH)
        assert _VALID_PATH in loader.cached_paths()

    def test_clear_cache_empties_cache(self):
        loader = PluginLoader()
        loader.load(_VALID_PATH)
        loader.clear_cache()
        assert loader.cached_paths() == []

    def test_multiple_paths_cached(self):
        loader = PluginLoader()
        loader.load(_VALID_PATH)
        loader.load(_VALID_PATH_2)
        assert len(loader.cached_paths()) == 2


# ── is_loadable ───────────────────────────────────────────────

class TestIsLoadable:

    def test_valid_path_is_loadable(self):
        loader = PluginLoader()
        assert loader.is_loadable(_VALID_PATH) is True

    def test_bad_module_not_loadable(self):
        loader = PluginLoader()
        assert loader.is_loadable(_BAD_MODULE) is False

    def test_bad_attribute_not_loadable(self):
        loader = PluginLoader()
        assert loader.is_loadable(_BAD_ATTR) is False

    def test_empty_string_not_loadable(self):
        loader = PluginLoader()
        assert loader.is_loadable("") is False


# ── Instantiation ─────────────────────────────────────────────

class TestInstantiate:

    def test_instantiate_valid_class(self):
        loader = PluginLoader()
        # Instantiate an OrderedDict with initial data
        instance = loader.instantiate(_VALID_PATH, None, [("a", 1)])
        from collections import OrderedDict
        assert isinstance(instance, OrderedDict)
        assert instance["a"] == 1

    def test_instantiate_bad_path_raises(self):
        loader = PluginLoader()
        with pytest.raises(PluginLoadError):
            loader.instantiate(_BAD_MODULE)

    def test_instantiate_with_kwargs(self):
        loader = PluginLoader()
        # defaultdict takes a callable as first arg
        instance = loader.instantiate(_VALID_PATH_2, None, list)
        from collections import defaultdict
        assert isinstance(instance, defaultdict)

    def test_instantiate_constructor_error_raises_plugin_load_error(self):
        loader = PluginLoader()
        # int("not_a_number") raises ValueError -- should be wrapped
        with pytest.raises(PluginLoadError, match="Failed to instantiate"):
            loader.instantiate("builtins.int", None, "not_a_number")
