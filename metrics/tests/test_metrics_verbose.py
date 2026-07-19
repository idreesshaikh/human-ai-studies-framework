"""Verbose metric-by-metric tests for the static-metrics leg.

Complements test_static_metrics.py (orchestrator/API surface) with exhaustive
per-metric cases: every tree-sitter metric gets exact hand-computed
expectations, every analyzer gets its documented edge cases, and the
duplicate-name/determinism guarantees of the parser are locked in as
regression tests.

Layout note: metrics/src is a flat script layout (no package), so it is put
on sys.path, same as test_static_metrics.py.
"""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analyzers import sonar_metrics  # noqa: E402
from analyzers.radon_metrics import (  # noqa: E402
    get_comment_ratio,
    get_halstead_effort,
)
from analyzers.sonar_metrics import get_cognitive_complexity  # noqa: E402
from analyzers.text_metrics import (  # noqa: E402
    get_indentation_variance,
    get_line_width_bounds,
)
from main import discover_python_files  # noqa: E402
from parsers.ts_parser import (  # noqa: E402
    collect_function_metrics,
    get_average_identifier_length,
    get_nesting_penalty,
    get_parameter_counts,
    get_variable_scope_distance,
    setup_parser,
)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def parse(source: str):
    """Parse a snippet and return (tree, language) for the metric functions."""
    parser, language = setup_parser()
    return parser.parse(textwrap.dedent(source).encode()), language


# ---------------------------------------------------------------------------
# Metric 1: parameter counts
# ---------------------------------------------------------------------------


class TestParameterCounts:
    def test_zero_params(self):
        tree, lang = parse("def f():\n    pass\n")
        assert get_parameter_counts(tree, lang) == {"f": 0}

    def test_positional_params(self):
        tree, lang = parse("def f(a, b, c):\n    pass\n")
        assert get_parameter_counts(tree, lang) == {"f": 3}

    def test_defaults_varargs_and_kwargs_each_count_once(self):
        tree, lang = parse("def f(a, b=1, *args, **kwargs):\n    pass\n")
        assert get_parameter_counts(tree, lang) == {"f": 4}

    def test_type_annotations_do_not_change_the_count(self):
        tree, lang = parse("def f(x: int, y: str = 'd') -> bool:\n    return True\n")
        assert get_parameter_counts(tree, lang) == {"f": 2}

    def test_self_counts_as_a_parameter(self):
        tree, lang = parse(
            """
            class C:
                def method(self, a):
                    pass
            """
        )
        assert get_parameter_counts(tree, lang) == {"method": 2}

    def test_nested_function_reported_separately(self):
        tree, lang = parse(
            """
            def outer(a, b):
                def inner(x):
                    return x
                return inner
            """
        )
        assert get_parameter_counts(tree, lang) == {"outer": 2, "inner": 1}

    def test_lambdas_are_not_functions(self):
        tree, lang = parse("f = lambda a, b: a + b\n")
        assert get_parameter_counts(tree, lang) == {}


# ---------------------------------------------------------------------------
# Metric 2: nesting penalty (2**depth per control-flow block)
# ---------------------------------------------------------------------------


class TestNestingPenalty:
    def test_flat_function_scores_zero(self):
        tree, lang = parse("def f():\n    return 1\n")
        assert get_nesting_penalty(tree, lang) == {"f": 0}

    @pytest.mark.parametrize(
        "block",
        [
            "if x:\n        pass",
            "for i in x:\n        pass",
            "while x:\n        pass",
            "with x:\n        pass",
            "try:\n        pass\n    except Exception:\n        pass",
        ],
        ids=["if", "for", "while", "with", "try"],
    )
    def test_every_control_flow_type_costs_one_at_depth_zero(self, block):
        tree, lang = parse(f"def f(x):\n    {block}\n")
        assert get_nesting_penalty(tree, lang) == {"f": 1}

    def test_nesting_doubles_the_cost_per_level(self):
        # if (2**0) > if (2**1) > if (2**2) = 7
        tree, lang = parse(
            """
            def f(x):
                if x:
                    if x:
                        if x:
                            pass
            """
        )
        assert get_nesting_penalty(tree, lang) == {"f": 7}

    def test_sibling_blocks_add_without_doubling(self):
        tree, lang = parse(
            """
            def f(x):
                if x:
                    pass
                if x:
                    pass
            """
        )
        assert get_nesting_penalty(tree, lang) == {"f": 2}

    def test_block_inside_except_clause_counts_as_nested(self):
        # try (2**0) + if inside the except clause (2**1) = 3
        tree, lang = parse(
            """
            def f(x):
                try:
                    pass
                except Exception:
                    if x:
                        pass
            """
        )
        assert get_nesting_penalty(tree, lang) == {"f": 3}

    def test_nested_function_blocks_count_for_both_functions(self):
        # function_definition itself adds no depth, so inner's if costs 2**0
        # in both walks: outer scores its own if (1) + inner's if (1) = 2.
        tree, lang = parse(
            """
            def outer(x):
                if x:
                    pass
                def inner(y):
                    if y:
                        pass
            """
        )
        penalties = get_nesting_penalty(tree, lang)
        assert penalties["inner"] == 1
        assert penalties["outer"] == 2


# ---------------------------------------------------------------------------
# Metric 3: average identifier length
# ---------------------------------------------------------------------------


class TestAverageIdentifierLength:
    def test_exact_average_over_every_identifier_occurrence(self):
        # identifiers: f(1) ab(2) cd(2) ab(2) cd(2) -> 9 chars / 5 = 1.8
        tree, lang = parse(
            """
            def f(ab):
                cd = ab
                return cd
            """
        )
        assert get_average_identifier_length(tree, lang) == {"f": 1.8}

    def test_result_is_rounded_to_two_decimals(self):
        # identifiers: g(1) x(1) abc(3) -> 5/3 = 1.666... -> 1.67
        tree, lang = parse("def g(x):\n    return abc\n")
        assert get_average_identifier_length(tree, lang) == {"g": 1.67}

    def test_attribute_and_call_names_count(self):
        result_tree, lang = parse(
            """
            def h():
                value.method()
            """
        )
        # h(1) value(5) method(6) -> 12/3 = 4.0
        assert get_average_identifier_length(result_tree, lang) == {"h": 4.0}


# ---------------------------------------------------------------------------
# Metric 4: variable scope distance
# ---------------------------------------------------------------------------


class TestVariableScopeDistance:
    def test_distance_is_lines_from_first_binding_to_last_use(self):
        tree, lang = parse(
            """
            def g():
                x = 1
                y = 2
                if x:
                    y += x
                return y
            """
        )
        # x: bound on its line, last read 3 lines later; same for y.
        assert get_variable_scope_distance(tree, lang) == {"g": {"x": 3, "y": 3}}

    def test_for_targets_and_walrus_bindings_are_declarations(self):
        tree, lang = parse(
            """
            def h(items):
                for i in items:
                    if (n := i * 2) > 4:
                        print(n)
            """
        )
        assert get_variable_scope_distance(tree, lang) == {"h": {"i": 1, "n": 1}}

    def test_parameters_are_not_tracked_as_locals(self):
        tree, lang = parse("def f(a):\n    return a\n")
        assert get_variable_scope_distance(tree, lang) == {"f": {}}

    def test_variable_never_read_again_has_distance_zero(self):
        tree, lang = parse("def f():\n    unused = 1\n    return 2\n")
        assert get_variable_scope_distance(tree, lang) == {"f": {"unused": 0}}

    def test_augmented_assignment_does_not_reset_the_declaration(self):
        tree, lang = parse(
            """
            def f():
                total = 0
                total += 1
                total += 2
                return total
            """
        )
        assert get_variable_scope_distance(tree, lang) == {"f": {"total": 3}}

    def test_variables_listed_in_declaration_order(self):
        tree, lang = parse(
            """
            def f():
                b = 1
                a = b
                return a + b
            """
        )
        assert list(get_variable_scope_distance(tree, lang)["f"]) == ["b", "a"]


# ---------------------------------------------------------------------------
# Parser-wide guarantees: duplicates and determinism
# ---------------------------------------------------------------------------

DUPLICATE_SOURCE = textwrap.dedent(
    """
    class A:
        def dup(self, a):
            x = 1
            return x

    class B:
        def dup(self, a, b, c):
            if a:
                return 1
    """
)


class TestDuplicateNamesAndDeterminism:
    def test_first_definition_wins_for_every_metric(self):
        rows = collect_function_metrics(DUPLICATE_SOURCE.encode())
        row = rows["dup"]  # A.dup: 2 params, no control flow
        assert row["parameter_count"] == 2
        assert row["nesting_penalty"] == 0

    def test_repeated_runs_are_byte_identical(self):
        # Regression: tree-sitter capture/match order is not guaranteed, so an
        # unsorted iteration made duplicate resolution flip between runs.
        results = {
            repr(collect_function_metrics(DUPLICATE_SOURCE.encode())) for _ in range(20)
        }
        assert len(results) == 1

    @pytest.mark.parametrize("corpus_file", ["weather.py", "detect.py"])
    def test_repeated_runs_on_real_corpus_are_identical(self, corpus_file):
        source = (CORPUS / corpus_file).read_bytes()
        results = {repr(collect_function_metrics(source)) for _ in range(10)}
        assert len(results) == 1

    def test_collect_aggregates_scope_distance_to_max_and_mean(self):
        source = "def g():\n    x = 1\n    y = 2\n    return x + y\n"
        row = collect_function_metrics(source.encode())["g"]
        assert row["max_scope_distance"] == 2  # x: decl line 1 -> use line 3
        assert row["mean_scope_distance"] == 1.5  # (2 + 1) / 2


# ---------------------------------------------------------------------------
# Text metrics
# ---------------------------------------------------------------------------


class TestIndentationVariance:
    def test_uniform_indentation_scores_zero(self):
        assert get_indentation_variance("a = 1\nb = 2\nc = 3\n") == 0.0

    def test_known_population_stdev(self):
        # widths 0, 2, 4 -> pstdev = 1.63
        assert get_indentation_variance("a\n  b\n    c\n") == 1.63

    def test_tabs_expand_to_four_spaces(self):
        # widths 4, 0 -> pstdev 2.0
        assert get_indentation_variance("\tx = 1\nx = 2\n") == 2.0

    def test_blank_lines_are_ignored(self):
        assert get_indentation_variance("a = 1\n\n\nb = 2\n") == 0.0

    def test_fewer_than_two_code_lines_is_zero(self):
        assert get_indentation_variance("") == 0.0
        assert get_indentation_variance("    lonely = 1\n") == 0.0


class TestLineWidthBounds:
    def test_max_and_mean_over_non_blank_lines(self):
        bounds = get_line_width_bounds("abcdef\n\nab\n")
        assert bounds == {"max_line_width": 6, "mean_line_width": 4.0}

    def test_tabs_expand_before_measuring(self):
        bounds = get_line_width_bounds("\tab\n12345\n")
        assert bounds == {"max_line_width": 6, "mean_line_width": 5.5}

    def test_empty_and_whitespace_only_sources_return_zeros(self):
        zeros = {"max_line_width": 0, "mean_line_width": 0.0}
        assert get_line_width_bounds("") == zeros
        assert get_line_width_bounds("   \n\t\n") == zeros


# ---------------------------------------------------------------------------
# Radon metrics
# ---------------------------------------------------------------------------


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
        # radon's raw.multi counts multi-line strings only; a one-line
        # docstring is invisible to this ratio.
        source = 'def f():\n    """Docs\n    over two lines."""\n    return 1\n'
        assert get_comment_ratio(source) > 0

    def test_uncommented_code_is_zero(self):
        assert get_comment_ratio("x = 1\ny = 2\n") == 0.0

    def test_empty_and_broken_sources_are_zero(self):
        assert get_comment_ratio("") == 0.0
        assert get_comment_ratio("def broken(:\n") == 0.0


# ---------------------------------------------------------------------------
# SonarQube client (stub-degradable)
# ---------------------------------------------------------------------------


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
        url = "http://127.0.0.1:9"  # discard port: connection refused
        assert get_cognitive_complexity("f.py", base_url=url, timeout=0.2) is None
        assert get_cognitive_complexity("f.py", base_url=url, timeout=0.2) is None
        err = capsys.readouterr().err
        assert err.count("not reachable") == 1


# ---------------------------------------------------------------------------
# Orchestrator: file discovery
# ---------------------------------------------------------------------------


class TestDiscoverPythonFiles:
    def test_finds_nested_python_files_sorted(self, tmp_path):
        (tmp_path / "b.py").write_text("x = 1\n", "utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.py").write_text("y = 2\n", "utf-8")
        found = discover_python_files(tmp_path)
        assert [p.name for p in found] == ["b.py", "a.py"]

    @pytest.mark.parametrize(
        "skip_dir", ["venv", ".venv", "__pycache__", "node_modules", ".git"]
    )
    def test_tooling_directories_are_skipped(self, tmp_path, skip_dir):
        (tmp_path / "keep.py").write_text("x = 1\n", "utf-8")
        hidden = tmp_path / skip_dir / "deep"
        hidden.mkdir(parents=True)
        (hidden / "skipped.py").write_text("y = 2\n", "utf-8")
        assert [p.name for p in discover_python_files(tmp_path)] == ["keep.py"]

    def test_non_python_files_are_ignored(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hi", "utf-8")
        assert discover_python_files(tmp_path) == []
