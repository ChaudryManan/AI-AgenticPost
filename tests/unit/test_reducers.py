"""State reducers — the merge functions that keep parallel writes sane."""
from __future__ import annotations

from smauto.state.reducers import merge_dict, merge_list, or_bool, take_last


def test_merge_dict_recursive():
    a = {"x": {"a": 1}, "y": 2}
    b = {"x": {"b": 3}}
    assert merge_dict(a, b) == {"x": {"a": 1, "b": 3}, "y": 2}


def test_merge_dict_scalar_overwrite():
    assert merge_dict({"x": 1}, {"x": 2}) == {"x": 2}


def test_merge_dict_with_none():
    assert merge_dict(None, {"x": 1}) == {"x": 1}
    assert merge_dict({"x": 1}, None) == {"x": 1}
    assert merge_dict(None, None) == {}


def test_merge_dict_nested_replacement():
    a = {"v": {"script": ["a"]}}
    b = {"v": {"clips": ["b"]}}
    assert merge_dict(a, b) == {"v": {"script": ["a"], "clips": ["b"]}}


def test_merge_list_concatenates():
    assert merge_list([1], [2, 3]) == [1, 2, 3]


def test_merge_list_with_none():
    assert merge_list(None, [1]) == [1]
    assert merge_list([1], None) == [1]


def test_take_last():
    assert take_last(1, 2) == 2
    assert take_last(None, 5) == 5


def test_or_bool():
    assert or_bool(False, False) is False
    assert or_bool(False, True) is True
    assert or_bool(True, False) is True
    assert or_bool(None, True) is True