"""
Measured detection rates for the non-compliance planner.

``PER_ROUTE`` maps each AI-access route to the sensitivity of StudyLoop's telemetry
on that route, and ``SPECIFICITY`` is its specificity, both from a labelled
calibration run. They stay ``None`` until real calibration results are filled in
here. While they are ``None`` the planner refuses a route mix, so nothing ever
assumes perfect detection by default.
"""

PER_ROUTE: dict[str, float] | None = None
SPECIFICITY: float | None = None
