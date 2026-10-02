import io
import json
import tempfile
import zipfile
from pathlib import Path

import yaml
from analysis.dataset import Dataset
from analysis.notebook import build_notebook, data_dictionary_markdown
from protocol.export import build_kit


def notebook_archive(protocol: dict, rows: list[dict], study_id: str) -> bytes:
    dataset = Dataset(rows=rows, study_id=study_id)
    files = {
        "notebook.ipynb": json.dumps(
            build_notebook(protocol, dataset, study_id), indent=1
        ),
        "data-dictionary.md": f"# {study_id}: data dictionary\n\n"
        + data_dictionary_markdown(dataset),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def replication_archive(protocol: dict, rows: list[dict], study_id: str) -> bytes:
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        protocol_path = staging / "protocol.yaml"
        protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
        output = staging / "replication-kit.tar.gz"
        build_kit(
            protocol_path,
            {"studyId": study_id, "rows": rows},
            output,
            repo_root=repo_root,
        )
        return output.read_bytes()
