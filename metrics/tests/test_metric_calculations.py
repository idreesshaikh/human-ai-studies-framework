"""Metric calculations on representative Python code and unavailable services."""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analyzers import sonar_metrics
from analyzers.radon_metrics import (
    get_comment_ratio,
    get_halstead_effort,
)
from analyzers.sonar_metrics import get_cognitive_complexity
from analyzers.text_metrics import (
    get_indentation_variance,
    get_line_width_bounds,
)
from main import discover_python_files
from parsers.ts_parser import (
    collect_function_metrics,
    get_average_identifier_length,
    get_nesting_penalty,
    get_parameter_counts,
    get_variable_scope_distance,
    setup_parser,
)


def parse(source: str):
    """Parse a snippet and return (tree, language) for the metric functions."""
    parser, language = setup_parser()
    return parser.parse(textwrap.dedent(source).encode()), language


def test_parameter_counts_include_methods_defaults_and_nested_functions():
    tree, lang = parse(
        """
        class Service:
            def run(self, items: list, enabled=True, *extra, **options):
                def accept(item):
                    return item
                return accept(items)
        def solo():
            pass
        transform = lambda a, b: a + b
        """
    )
    assert get_parameter_counts(tree, lang) == {"run": 5, "accept": 1, "solo": 0}


def test_nesting_penalty_accounts_for_depth_siblings_and_exception_handlers():
    tree, lang = parse(
        """
        def nested(x):
            if x:
                if x:
                    if x:
                        pass
        def siblings(x):
            if x:
                pass
            if x:
                pass
        def guarded(x):
            try:
                with x:
                    pass
            except Exception:
                while x:
                    for item in x:
                        pass
        def outer(x):
            if x:
                pass
            def inner(y):
                if y:
                    pass
        def plain():
            return 1
        """
    )
    assert get_nesting_penalty(tree, lang) == {
        "nested": 7,
        "siblings": 2,
        "guarded": 9,
        "outer": 2,
        "inner": 1,
        "plain": 0,
    }


def test_average_identifier_length_counts_occurrences_calls_and_attributes():
    tree, lang = parse(
        """
        def f(ab):
            cd = ab
            return cd
        def g(x):
            return abc
        def h():
            value.method()
        """
    )
    assert get_average_identifier_length(tree, lang) == {"f": 1.8, "g": 1.67, "h": 4.0}


def test_scope_distance_uses_first_binding_and_last_use_without_tracking_parameters():
    source = textwrap.dedent(
        """
        def g(a):
            x = 1
            y = 2
            unused = 0
            if x:
                y += x
            return y + a
        def walrus(items):
            for i in items:
                if (n := i * 2) > 4:
                    print(n)
        def sum_values():
            total = 0
            total += 1
            total += 2
            return total
        def identity(a):
            return a
        """
    )
    tree, lang = parse(source)
    assert get_variable_scope_distance(tree, lang) == {
        "g": {"x": 4, "y": 4, "unused": 0},
        "walrus": {"i": 1, "n": 1},
        "sum_values": {"total": 3},
        "identity": {},
    }
    row = collect_function_metrics(source.encode())["g"]
    assert row["max_scope_distance"] == 4
    assert row["mean_scope_distance"] == 2.67


@pytest.mark.parametrize(
    "source,variance,width",
    [
        ("abcdef\n\nab\n", 0.0, {"max_line_width": 6, "mean_line_width": 4.0}),
        ("a\n  b\n    c\n", 1.63, {"max_line_width": 5, "mean_line_width": 3.0}),
        ("\tab\n12345\n", 2.0, {"max_line_width": 6, "mean_line_width": 5.5}),
        ("   \n\t\n", 0.0, {"max_line_width": 0, "mean_line_width": 0.0}),
        ("    lonely = 1\n", 0.0, {"max_line_width": 14, "mean_line_width": 14.0}),
    ],
)
def test_text_metrics_ignore_blank_lines_and_expand_tabs(source, variance, width):
    assert get_indentation_variance(source) == variance
    assert get_line_width_bounds(source) == width


class TestHalsteadEffort:
    def test_total_and_per_function_reported(self):
        report = get_halstead_effort("def f(a, b):\n    return a * b + a / b\n")
        assert report["total"] > 0
        assert report["functions"]["f"] > 0

    def test_effortless_code_scores_zero(self):
        assert get_halstead_effort("x = 1\n")["functions"] == {}

    def test_duplicate_function_names_keep_first_occurrence(self):
        source = textwrap.dedent(
            """
            def f(a, b):
                return a * b + a - b

            def f(a):
                return a
            """
        )
        first_only = get_halstead_effort("def f(a, b):\n    return a * b + a - b\n")
        report = get_halstead_effort(source)
        assert list(report["functions"]) == ["f"]
        assert report["functions"]["f"] == first_only["functions"]["f"]

    def test_syntax_errors_degrade_to_zero(self):
        assert get_halstead_effort("def broken(:\n") == {
            "total": 0.0,
            "functions": {},
        }


class TestCommentRatio:
    def test_comment_lines_over_sloc(self):
        assert get_comment_ratio("# a\n# b\nx = 1\n") == 2.0

    def test_multiline_docstrings_count_as_documentation(self):
        source = 'def f():\n    """Docs\n    over two lines."""\n    return 1\n'
        assert get_comment_ratio(source) > 0

    def test_uncommented_code_is_zero(self):
        assert get_comment_ratio("x = 1\ny = 2\n") == 0.0

    def test_empty_and_broken_sources_are_zero(self):
        assert get_comment_ratio("") == 0.0
        assert get_comment_ratio("def broken(:\n") == 0.0


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestCognitiveComplexity:
    @pytest.fixture(autouse=True)
    def reset_warning_flag(self, monkeypatch):
        monkeypatch.setattr(sonar_metrics, "_warned", False)

    def test_reachable_server_returns_the_measure(self, monkeypatch):
        payload = {
            "component": {
                "measures": [{"metric": "cognitive_complexity", "value": "7"}]
            }
        }
        monkeypatch.setattr(
            sonar_metrics.requests, "get", lambda *a, **k: FakeResponse(payload)
        )
        assert get_cognitive_complexity("some/file.py") == 7.0

    def test_component_without_measures_returns_none(self, monkeypatch):
        payload = {"component": {"measures": []}}
        monkeypatch.setattr(
            sonar_metrics.requests, "get", lambda *a, **k: FakeResponse(payload)
        )
        assert get_cognitive_complexity("some/file.py") is None

    def test_token_is_passed_as_basic_auth(self, monkeypatch):
        seen = {}

        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return FakeResponse({"component": {"measures": []}})

        monkeypatch.setattr(sonar_metrics.requests, "get", fake_get)
        get_cognitive_complexity("f.py", token="secret")
        assert seen["auth"] == ("secret", "")

    def test_unreachable_server_degrades_to_none_and_warns_once(self, capsys):
        url = "http://127.0.0.1:9"
        assert get_cognitive_complexity("f.py", base_url=url, timeout=0.2) is None
        assert get_cognitive_complexity("f.py", base_url=url, timeout=0.2) is None
        err = capsys.readouterr().err
        assert err.count("not reachable") == 1


def test_discovers_only_project_python_files_in_stable_order(tmp_path):
    (tmp_path / "b.py").write_text("x = 1\n", "utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.py").write_text("y = 2\n", "utf-8")
    (tmp_path / "notes.txt").write_text("notes", "utf-8")
    for directory in ["venv", ".venv", "__pycache__", "node_modules", ".git"]:
        hidden = tmp_path / directory / "deep"
        hidden.mkdir(parents=True)
        (hidden / "skipped.py").write_text("z = 3\n", "utf-8")
    assert [
        path.relative_to(tmp_path).as_posix()
        for path in discover_python_files(tmp_path)
    ] == ["b.py", "sub/a.py"]
