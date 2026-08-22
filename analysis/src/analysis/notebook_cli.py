"""CLI wiring for the `notebook` subcommand (curated handoff)."""

from __future__ import annotations

from pathlib import Path

from analysis.notebook import write_notebook


def cmd_notebook(protocol: dict, dataset, study_id: str, args) -> int:
    out_dir = Path(args.out) / study_id
    if args.dictionary_only:
        out_dir.mkdir(parents=True, exist_ok=True)
        from analysis.notebook import data_dictionary_markdown

        path = out_dir / "data-dictionary.md"
        header = f"# {study_id}  -  data dictionary\n\n"
        path.write_text(header + data_dictionary_markdown(dataset))
        print(f"data dictionary: {path}")
        return 0
    nb_path, dd_path = write_notebook(protocol, dataset, study_id, out_dir)
    print(f"starter notebook: {nb_path}")
    print(f"data dictionary: {dd_path}")
    print("open it: jupyter lab " + str(nb_path))
    return 0
