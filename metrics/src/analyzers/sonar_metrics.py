"""SonarQube Cognitive Complexity client - stub-degradable (decision D5).

Cognitive Complexity is the one industry-baseline metric in the matrix
(metrics/docs/static_code_metrics.md, "Structural & Control Flow"); we query it
from a local SonarQube rather than reimplementing it, so our numbers stay
comparable to industry tooling.

Follow-up to activate (documented, not required for the pipeline to run):
    docker run -d -p 9000:9000 sonarqube:community
    # run sonar-scanner over the target project, then re-run the orchestrator
Until a server is reachable, get_cognitive_complexity() returns None (NaN in
the exported tables) and the orchestrator warns once per run, not per file.
"""

import sys

import requests

_warned = False


def get_cognitive_complexity(
    file_path: str,
    base_url: str = "http://localhost:9000",
    token: str | None = None,
    timeout: float = 1.5,
) -> float | None:
    """Fetch cognitive_complexity for a component from SonarQube's Web API.

    Returns None (and warns once per process) when the server is unreachable
    or the component is unknown - analysis degrades to NaN, never crashes.
    """
    global _warned
    auth = (token, "") if token else None
    try:
        response = requests.get(
            f"{base_url}/api/measures/component",
            params={"component": file_path, "metricKeys": "cognitive_complexity"},
            auth=auth,
            timeout=timeout,
        )
        response.raise_for_status()
        measures = response.json()["component"]["measures"]
        if not measures:
            return None
        return float(measures[0]["value"])
    except (requests.RequestException, KeyError, ValueError, IndexError):
        if not _warned:
            print(
                f"[sonar_metrics] SonarQube not reachable at {base_url}; "
                "cognitive_complexity will be NaN (see module docstring to "
                "enable it).",
                file=sys.stderr,
            )
            _warned = True
        return None
