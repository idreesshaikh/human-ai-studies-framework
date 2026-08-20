import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor


def setup_parser():
    """Initializes and returns the Python tree-sitter parser"""
    py_language = Language(tspython.language())
    parser = Parser(py_language)
    return parser, py_language


def _text(node) -> str:
    """Decodes a node's source text."""
    return node.text.decode("utf8")


def _captures(language: Language, query_string: str, node, capture_name: str) -> list:
    """Runs a query on a node and returns the nodes captured under capture_name."""
    query = Query(language, query_string)
    cursor = QueryCursor(query)
    return cursor.captures(node).get(capture_name, [])


def _iter_functions(tree, language: Language):
    """Yields (func_name, func_node) for every function definition."""
    query = Query(
        language,
        """
        (function_definition
            name: (identifier) @func_name
        ) @func_node
        """,
    )
    cursor = QueryCursor(query)
    pairs = [
        (captures["func_name"][0], captures["func_node"][0])
        for _, captures in cursor.matches(tree.root_node)
    ]

    seen = set()
    for name_node, func_node in sorted(pairs, key=lambda p: p[1].start_byte):
        func_name = _text(name_node)
        if func_name in seen:
            continue
        seen.add(func_name)
        yield func_name, func_node


def get_parameter_counts(tree, language: Language) -> dict:
    """
    Parses Python code and returns a dictionary mapping function names to their
    parameter counts.
    """
    results = {}
    for func_name, func_node in _iter_functions(tree, language):
        param_block = func_node.child_by_field_name("parameters")
        if param_block is None:
            continue

        results[func_name] = len(param_block.named_children)

    return results


def _calculate_node_penalty(node, current_depth: int) -> int:
    """Recursively walks an AST node."""
    penalty = 0
    nesting_types = {
        "if_statement",
        "for_statement",
        "while_statement",
        "try_statement",
        "with_statement",
    }

    if node.type in nesting_types:
        penalty += 2**current_depth
        current_depth += 1

    for child in node.named_children:
        penalty += _calculate_node_penalty(child, current_depth)

    return penalty


def get_nesting_penalty(tree, language: Language) -> dict:
    """Extracts the total nesting penalty score per function"""
    return {
        func_name: _calculate_node_penalty(func_node, current_depth=0)
        for func_name, func_node in _iter_functions(tree, language)
    }


def get_average_identifier_length(tree, language: Language) -> dict:
    """
    Calculates the average length of identifiers (variable names, function names) per
    function.
    """
    results = {}
    for func_name, func_node in _iter_functions(tree, language):
        identifiers = _captures(language, "(identifier) @id", func_node, "id")
        if not identifiers:
            continue

        total_length = sum(len(_text(node)) for node in identifiers)

        results[func_name] = round(total_length / len(identifiers), 2)

    return results


def get_variable_scope_distance(tree, language: Language) -> dict:
    """
    For every local variable, the distance is the line-count delta between where it is
    first declared (i.e. first bound/assigned) and where it is last used.
    """
    target_query_string = """
    (assignment left: (identifier) @target)
    (augmented_assignment left: (identifier) @target)
    (for_statement left: (identifier) @target)
    (named_expression name: (identifier) @target)
    """

    results = {}
    for func_name, func_node in _iter_functions(tree, language):
        decl_line = {}
        for node in _captures(language, target_query_string, func_node, "target"):
            name = _text(node)
            line = node.start_point[0]
            if name not in decl_line or line < decl_line[name]:
                decl_line[name] = line

        last_use = {}
        for node in _captures(language, "(identifier) @use", func_node, "use"):
            name = _text(node)
            if name not in decl_line:
                continue
            line = node.start_point[0]
            if name not in last_use or line > last_use[name]:
                last_use[name] = line

        results[func_name] = {
            name: last_use[name] - decl_line[name]
            for name in sorted(decl_line, key=lambda n: decl_line[n])
        }

    return results


def collect_function_metrics(source_bytes: bytes) -> dict:
    """
    Run all four tree-sitter metrics over one source file and return per-function rows
    ready for tabular export.
    """
    parser, language = setup_parser()
    tree = parser.parse(source_bytes)

    params = get_parameter_counts(tree, language)
    nesting = get_nesting_penalty(tree, language)
    ident_len = get_average_identifier_length(tree, language)
    scope = get_variable_scope_distance(tree, language)

    results = {}
    for name in params.keys() | nesting.keys() | ident_len.keys() | scope.keys():
        distances = list(scope.get(name, {}).values())
        mean_dist = round(sum(distances) / len(distances), 2) if distances else 0.0
        results[name] = {
            "parameter_count": params.get(name),
            "nesting_penalty": nesting.get(name),
            "avg_identifier_length": ident_len.get(name),
            "max_scope_distance": max(distances) if distances else 0,
            "mean_scope_distance": mean_dist,
        }
    return results


if __name__ == "__main__":
    from pathlib import Path

    target_file = Path(__file__).resolve().parents[2] / "corpus" / "detect.py"

    with open(target_file, "rb") as f:
        sample_code = f.read()

    parser, lang = setup_parser()
    tree = parser.parse(sample_code)

    print("--- Static Metrics Extraction ---")

    print("\n1. Parameter Counts:")
    params = get_parameter_counts(tree, lang)
    for func, count in params.items():
        print(f" - {func}: {count}")

    print("\n2. Nesting Depth Penalty:")
    nesting = get_nesting_penalty(tree, lang)
    for func, score in nesting.items():
        print(f" - {func}: Score {score}")

    print("\n3. Average Identifier Length:")
    avg_lengths = get_average_identifier_length(tree, lang)
    for func, avg_len in avg_lengths.items():
        print(f" - {func}: {avg_len} chars")

    print("\n4. Variable Scope Distance (lines between declaration and last use):")
    scope = get_variable_scope_distance(tree, lang)
    for func, variables in scope.items():
        print(f" - {func}:")
        for var, dist in variables.items():
            print(f"     {var}: {dist} lines")
