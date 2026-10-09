"""Unit tests for the pure protocol compiler's template resilience."""

import yaml

from middleware import compiler


def _rq_move() -> dict:
    return {
        "moveId": "m-rq",
        "kind": "add-rq",
        "target": "researchQuestions[]",
        "proposal": "Do junior developers over-trust AI-generated code?",
        "patch": {
            "section": "researchQuestions",
            "op": "append",
            "value": "Do junior developers over-trust AI-generated code?",
        },
        "grounding": [],
        "status": "accepted",
    }


def _template_move(move_id: str, template_id: str, parameters: dict) -> dict:
    return {
        "moveId": move_id,
        "kind": "choose-template",
        "target": "design",
        "proposal": f"Use {template_id}.",
        "patch": {"templateId": template_id, "parameters": parameters},
        "grounding": [],
        "status": "accepted",
    }


def _merge_move(move_id: str, template_ids: list[str], reason: str) -> dict:
    return {
        "moveId": move_id,
        "kind": "merge-templates",
        "target": "design",
        "proposal": f"Merge {', '.join(template_ids)}.",
        "patch": {"templateIds": template_ids, "reason": reason},
        "grounding": [],
        "status": "accepted",
    }


def test_hallucinated_template_id_reports_instead_of_raising():
    """
    The original bug: an accepted choose-template move naming a template the registry
    doesn't have crashed the compile.
    """
    result = compiler.compile_moves(
        [_rq_move(), _template_move("m-t", "hallucinated-rct-2026", {})]
    )
    assert result.yaml.strip(), "the draft must never come back empty"
    assert not result.valid
    assert any("hallucinated-rct-2026" in e for e in result.errors)
    assert "the design" in result.unresolved


def test_a_seeded_draft_survives_the_first_zero_move_compile():
    """
    A study created from "derive from paper" or "merge templates" (`app.py`'s
    `create_study` writes the seed protocol as the study's `ProtocolDraftRow`,
    which the caller passes back in as `base_yaml`) auto-compiles once on
    landing, before any move exists. With no template move to instantiate,
    the compiler used to fall straight to a bare scaffold, discarding the
    seed entirely  -  silently breaking the promise both promotion flows make
    ("this design seeds its draft, citing the paper"/"the merged protocol").
    """
    seed = {
        "protocolVersion": 4,
        "study": {
            "id": "draft",
            "title": "Seeded from a paper",
            "researchers": ["Researcher"],
        },
        "researchQuestions": [{"id": "RQ-1", "text": "Does the seed survive?"}],
        "phases": [{"name": "design", "gates": []}],
    }
    result = compiler.compile_moves([], base_yaml=yaml.safe_dump(seed))
    assert "Seeded from a paper" in result.yaml
    assert "Does the seed survive?" in result.yaml

    # A move layers on top of the seed exactly as it would on a
    # template-instantiated base, rather than replacing it.
    with_move = compiler.compile_moves([_rq_move()], base_yaml=yaml.safe_dump(seed))
    assert "Seeded from a paper" in with_move.yaml
    assert "over-trust AI-generated code" in with_move.yaml


def test_garbage_base_yaml_falls_back_to_the_blank_scaffold():
    """Not every base_yaml is a real seed  -  an in-progress draft with no
    template and no seed still starts clean, and outright junk never crashes
    the compile."""
    result = compiler.compile_moves([], base_yaml="not: a, protocol")
    assert result.yaml.strip()
    assert "study" in result.yaml


def test_unknown_parameters_are_ignored_with_a_warning():
    """
    An LLM-invented parameter name doesn't sink an otherwise-sound template choice  -
    it's dropped, noted, and the template still applies.
    """
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {"bogusParam": 999})]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert any("bogusParam" in w for w in result.warnings)
    assert not result.errors


def test_last_instantiable_template_wins_over_a_broken_later_one():
    """
    A broken accepted template move is skipped in favour of the most recent one that
    instantiates, and the skip is reported as a warning  -  a valid draft isn't blocked
    on a move nobody can un-accept.
    """
    result = compiler.compile_moves(
        [
            _rq_move(),
            _template_move("m-good", "two-group-rct-v1", {}),
            _template_move("m-bad", "hallucinated-rct-2026", {}),
        ]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    assert any("hallucinated-rct-2026" in w for w in result.warnings)


def test_list_valued_patch_flattens_into_string_entries():
    """A move that packs several entries into one list value ("Two conditions: A vs."""
    conditions = {
        "moveId": "m-c",
        "kind": "set-parameter",
        "target": "conditions",
        "proposal": "Two conditions.",
        "patch": {
            "section": "conditions",
            "op": "append",
            "value": ["AI-assisted", "Traditional resources"],
        },
        "grounding": [],
        "status": "accepted",
    }
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {}), conditions]
    )
    assert result.valid, result.errors
    assert "AI-assisted" in result.draft["conditions"]
    assert "Traditional resources" in result.draft["conditions"]
    assert all(isinstance(c, str) for c in result.draft["conditions"])


def test_broken_template_before_a_working_one_stays_silent():
    """
    Last-wins semantics unchanged: when the newest accepted template move instantiates,
    earlier ones  -  broken or not  -  are simply superseded.
    """
    result = compiler.compile_moves(
        [
            _template_move("m-bad", "hallucinated-rct-2026", {}),
            _template_move("m-good", "two-group-rct-v1", {}),
        ]
    )
    assert result.template_id == "two-group-rct-v1"
    assert result.valid
    # The template's own content is announced, but the superseded one stays silent.
    assert not any("hallucinated" in w for w in result.warnings)
    assert all(w.startswith("From the") for w in result.warnings)
    assert result.errors == []


def test_accepted_merge_templates_compiles_into_the_draft():
    """
    Phase 5: an accepted merge-templates move composes its shapes into one grounded
    protocol  -  the RQs and literature of every merged template survive, renumbered.
    """
    result = compiler.compile_moves(
        [
            _merge_move(
                "m-merge",
                ["metr-rct-v1", "survey-self-report-v1"],
                "Objective behaviour data plus self-report perception.",
            )
        ]
    )
    assert result.valid, result.errors
    assert result.template_id is None  # a merge has no single template
    assert result.draft["study"]["title"].startswith("Merged design")
    # Both templates' research questions survive the merge, renumbered.
    assert len(result.draft["researchQuestions"]) >= 3
    # The merged protocol names every paper it drew from.
    refs = {lit["paperRef"] for lit in result.draft["literature"]}
    assert "arxiv:2507.09089" in refs
    assert result.errors == []


def test_merge_with_a_hallucinated_template_reports_instead_of_raising():
    """
    A merge naming an unknown template must not crash the compile  -  same lenient
    contract as a hallucinated choose-template.
    """
    result = compiler.compile_moves(
        [
            _merge_move(
                "m-merge",
                ["metr-rct-v1", "hallucinated-rct-2026"],
                "Both shapes are needed.",
            )
        ]
    )
    assert result.yaml.strip(), "the draft must never come back empty"
    assert not result.valid
    assert any("hallucinated-rct-2026" in e for e in result.errors)
    assert "the design" in result.unresolved


def test_merge_supersedes_an_earlier_single_template():
    """
    Last-wins across design-shape moves: a newer merge replaces an older accepted
    single template, the way one template choice already replaces another.
    """
    result = compiler.compile_moves(
        [
            _template_move("m-single", "two-group-rct-v1", {}),
            _merge_move(
                "m-merge",
                ["metr-rct-v1", "survey-self-report-v1"],
                "Both shapes are needed.",
            ),
        ]
    )
    assert result.valid, result.errors
    assert result.draft["study"]["title"].startswith("Merged design")
    assert result.template_id is None


# ------------------------------------------------ user values beat compiler defaults


def _tern_move(config: dict, move_id: str = "m-tern") -> dict:
    return {
        "moveId": move_id,
        "kind": "add-instrument",
        "target": "instruments",
        "proposal": "Capture with TERN.",
        "patch": {
            "section": "instruments",
            "op": "add-instrument",
            "name": "tern",
            "config": config,
        },
        "grounding": [],
        "status": "accepted",
    }


def _field_move(path: list[str], value, move_id: str = "m-field") -> dict:
    return {
        "moveId": move_id,
        "kind": "set-field",
        "target": ".".join(path),
        "proposal": "Set it.",
        "patch": {"op": "set-field", "path": path, "value": value},
        "grounding": [],
        "status": "accepted",
    }


def test_partial_tern_config_keeps_supplied_values_and_fills_only_missing():
    config = {
        "session": {"durationMinutes": 30},
        "fatigue": {"intervalMinutes": 10},
    }
    result = compiler.compile_moves([_rq_move(), _tern_move(config)])
    tern = result.draft["instruments"]["tern"]
    assert tern["session"]["durationMinutes"] == 30
    assert tern["fatigue"]["intervalMinutes"] == 10
    assert tern["fatigue"]["jitterPercent"] == 20  # missing key filled
    assert tern["stuck"]["enabled"] is True  # missing section filled
    assert "Standard TERN capture settings were added." in result.warnings
    assert not any("filled incomplete" in w for w in result.warnings)


def test_accepted_session_duration_slot_is_merged_into_the_tern_config():
    moves = [
        _rq_move(),
        _tern_move({}),
        _field_move(["session", "durationMinutes"], 30),
    ]
    result = compiler.compile_moves(moves)
    assert result.draft["session"]["durationMinutes"] == 30
    assert result.draft["instruments"]["tern"]["session"]["durationMinutes"] == 30


def test_session_duration_slot_wins_over_a_default_whatever_the_move_order():
    moves = [
        _field_move(["session", "durationMinutes"], 30),
        _rq_move(),
        _tern_move({"fatigue": {"intervalMinutes": 10}}),
    ]
    tern = compiler.compile_moves(moves).draft["instruments"]["tern"]
    assert tern["session"]["durationMinutes"] == 30
    assert tern["fatigue"]["intervalMinutes"] == 10


def test_legacy_task_timer_remap_keeps_nested_minutes_including_45():
    assert (
        compiler._session_minutes_from_config(
            {"capture": {"session": {"durationMinutes": 45}}}, default=30
        )
        == 45
    )
    assert compiler._session_minutes_from_config({}, default=30) == 30
    assert compiler._session_minutes_from_config({"minutes": 20}, default=30) == 20


def test_accepted_duration_slot_also_sizes_a_template_brought_tern_config():
    moves = [
        _template_move("m-t", "metr-rct-v1", {}),
        _field_move(["session", "durationMinutes"], 30),
    ]
    draft = compiler.compile_moves(moves).draft
    assert draft["session"]["durationMinutes"] == 30
    assert draft["instruments"]["tern"]["session"]["durationMinutes"] == 30


def test_a_later_accepted_slot_move_overrides_an_earlier_one():
    planned = ["participants", "planned"]
    moves = [
        _rq_move(),
        _field_move(planned, 12, "m-a"),
        _field_move(planned, 20, "m-b"),
    ]
    assert compiler.compile_moves(moves).draft["participants"]["planned"] == 20
    # A rejected later move does not override.
    later = _field_move(planned, 99, "m-c")
    later["status"] = "rejected"
    assert (
        compiler.compile_moves([*moves, later]).draft["participants"]["planned"] == 20
    )


def _task_move(text: str, **extra) -> dict:
    patch = {"id": "refactor", "title": "Refactor task", "description": text, **extra}
    return {
        "moveId": "m-task",
        "kind": "declare-task",
        "target": "tasks[]",
        "proposal": text,
        "patch": patch,
        "grounding": [],
        "status": "accepted",
    }


def _crossover() -> dict:
    return _template_move("m-t", "within-subjects-crossover-v1", {})


def test_session_length_stated_in_a_declared_task_replaces_the_template_default():
    moves = [_crossover(), _task_move("30 minutes per condition on one refactor")]
    draft = compiler.compile_moves(moves).draft
    assert draft["session"]["durationMinutes"] == 30
    assert draft["instruments"]["tern"]["session"]["durationMinutes"] == 30


def test_session_length_is_read_from_the_task_proposal_text_and_hyphenated_forms():
    move = _task_move("Fix a failing test")
    move["proposal"] = "A 20-minute task per condition"
    draft = compiler.compile_moves([_crossover(), move]).draft
    assert draft["session"]["durationMinutes"] == 20
    move = _task_move("Budget 25 min for the refactor")
    draft = compiler.compile_moves([_crossover(), move]).draft
    assert draft["session"]["durationMinutes"] == 25


def test_explicit_duration_slot_beats_minutes_found_in_task_text():
    moves = [
        _crossover(),
        _task_move("30 minutes per condition"),
        _field_move(["session", "durationMinutes"], 60),
    ]
    draft = compiler.compile_moves(moves).draft
    assert draft["session"]["durationMinutes"] == 60
    assert draft["instruments"]["tern"]["session"]["durationMinutes"] == 60


def test_an_assumed_default_session_length_is_warned_about():
    result = compiler.compile_moves([_crossover()])
    assert result.draft["session"]["durationMinutes"] == 45
    assert "Session length was not stated, so 45 minutes was assumed" in result.warnings


def test_no_assumed_length_warning_when_the_length_was_stated():
    stated = compiler.compile_moves(
        [_crossover(), _field_move(["session", "durationMinutes"], 30)]
    )
    from_task = compiler.compile_moves([_crossover(), _task_move("30 minutes each")])
    for result in (stated, from_task):
        assert not any("was not stated" in w for w in result.warnings)


def _measure_move(text: str, move_id: str) -> dict:
    return {
        "moveId": move_id,
        "kind": "add-measure",
        "target": "measures[]",
        "proposal": f"Measure {text}.",
        "patch": {"section": "measures", "op": "append", "value": text},
        "grounding": [],
        "status": "accepted",
    }


def test_template_supplied_items_get_one_plain_warning_each():
    result = compiler.compile_moves([_rq_move(), _crossover()])
    notes = [w for w in result.warnings if w.startswith("From the")]
    assert (
        notes[0].startswith("From the Within-subjects crossover template: ")
        and "research question 1" in notes[0]
    )
    rq2 = next(n for n in notes if "research question 2" in n)
    assert '"' in rq2 and "(you did not state it; remove it if unwanted)" in rq2
    assert "From the template: the NASA-TLX cognitive-load measure set." in notes
    assert (
        "From the template: the paired nonparametric test and the NASA-TLX "
        "debrief analysis." in notes
    )
    joined = " ".join(notes)
    for leaked in (
        "within-subjects-crossover-v1",
        "RQ-1",
        "RQ-2",
        "cognitive-load-9",
        "paired-nonparametric",
        "tlx-debrief",
        "Added from",
    ):
        assert leaked not in joined
    # Nothing was deleted: the template's content is still in the draft.
    assert [rq["id"] for rq in result.draft["researchQuestions"]][:2] == [
        "RQ-1",
        "RQ-2",
    ]


def test_a_research_question_the_researcher_stated_is_not_credited_to_the_template():
    stated = "How do participants perceive the AI-assisted vs unassisted experience?"
    rq = _rq_move()
    rq["patch"]["value"] = stated
    notes = [
        w
        for w in compiler.compile_moves([rq, _crossover()]).warnings
        if w.startswith("From the")
    ]
    assert not any("research question 2" in n for n in notes)
    assert any("research question 1" in n for n in notes)


def test_no_template_means_no_added_from_template_warning():
    result = compiler.compile_moves([_rq_move()])
    assert not any(w.startswith("From the") for w in result.warnings)


def test_measure_that_is_another_plus_a_unit_is_deduplicated_keeping_the_specific_one():
    moves = [
        _crossover(),
        _measure_move("task completion time", "m1"),
        _measure_move("Task completion time (seconds)", "m2"),
        _measure_move("Correctness", "m3"),
    ]
    result = compiler.compile_moves(moves)
    assert result.draft["measures"] == ["Task completion time (seconds)", "Correctness"]
    assert any(
        w.startswith("Dropped") and "task completion time" in w for w in result.warnings
    )


def test_measures_that_differ_only_in_case_are_deduplicated():
    moves = [
        _crossover(),
        _measure_move("Task completion time (seconds)", "m1"),
        _measure_move("task COMPLETION time", "m2"),
    ]
    assert compiler.compile_moves(moves).draft["measures"] == [
        "Task completion time (seconds)"
    ]


def test_task_conditions_reuse_the_protocols_canonical_condition_names():
    task = _task_move("Refactor", conditions=["AI-assisted", "unassisted", "extra"])
    draft = compiler.compile_moves([_crossover(), task]).draft
    assert draft["conditions"] == ["ai-assisted", "unassisted"]
    assert draft["tasks"][0]["conditions"] == ["ai-assisted", "unassisted", "extra"]


def _condition_move(text: str, move_id: str) -> dict:
    return {
        "moveId": move_id,
        "kind": "add-condition",
        "target": "conditions[]",
        "proposal": f"Compare {text}.",
        "patch": {"section": "conditions", "op": "append", "value": text},
        "grounding": [],
        "status": "accepted",
    }


def test_case_variant_conditions_are_collapsed_keeping_the_first_spelling():
    moves = [
        _crossover(),
        _condition_move("AI-assisted", "c1"),
        _condition_move("Unassisted", "c2"),
        _task_move("Fix a bug", conditions=["AI-ASSISTED", "unassisted"]),
    ]
    draft = compiler.compile_moves(moves).draft
    assert draft["conditions"] == ["ai-assisted", "unassisted"]
    assert draft["tasks"][0]["conditions"] == ["ai-assisted", "unassisted"]


def test_a_measure_combining_two_other_measures_is_dropped():
    moves = [
        _crossover(),
        _measure_move("task completion time", "m1"),
        _measure_move("solution correctness", "m2"),
        _measure_move("Task completion time and solution correctness", "m3"),
    ]
    result = compiler.compile_moves(moves)
    assert result.draft["measures"] == ["task completion time", "solution correctness"]
    assert any(
        w.startswith("Dropped the duplicate measure")
        and "Task completion time and solution correctness" in w
        for w in result.warnings
    )


def test_standard_tern_placeholders_raise_no_unsupported_or_key_list_warning():
    config = dict.fromkeys(("session", "fatigue", "stuck", "output"), "standard")
    result = compiler.compile_moves([_rq_move(), _tern_move(config)])
    tern = result.draft["instruments"]["tern"]
    assert tern == {**compiler.default_capture_instrument(45)}
    assert not any("unsupported" in w for w in result.warnings)
    assert not any(
        "durationMinutes" in w or "intervalMinutes" in w for w in result.warnings
    )
    assert "Standard TERN capture settings were added." in result.warnings


def test_genuinely_unsupported_tern_fields_are_still_reported_in_plain_words():
    config = {"session": {"durationMinutes": 30, "colour": "red"}, "bogus": {}}
    warnings = compiler.compile_moves([_rq_move(), _tern_move(config)]).warnings
    note = next(w for w in warnings if "not supported" in w)
    assert "colour" in note and "bogus" in note


def test_manual_entry_supersedes_earlier_moves_but_not_later_ones():
    def title(move_id: str, value: str) -> dict:
        return {
            "moveId": move_id,
            "kind": "set-field",
            "target": "study.title",
            "proposal": value,
            "patch": {"op": "set-field", "path": ["study", "title"], "value": value},
            "grounding": [],
            "status": "accepted",
        }

    manual = _template_move("m-manual", "two-group-rct-v1", {"title": "Manual"})
    manual["patch"]["manual"] = True
    before = [_rq_move(), title("m-old", "Conversation")]

    result = compiler.compile_moves([*before, manual])
    assert result.draft["study"]["title"] == "Manual"
    assert _rq_move()["proposal"] not in [
        rq["text"] for rq in result.draft["researchQuestions"]
    ]

    later = compiler.compile_moves([*before, manual, title("m-new", "Refined")])
    assert later.draft["study"]["title"] == "Refined"


def test_placeholder_researcher_name_is_obviously_editable_and_still_valid():
    for result in (
        compiler.compile_moves([_rq_move(), _crossover()]),
        compiler.compile_moves([_rq_move()]),
    ):
        assert result.draft["study"]["researchers"] == ["Lead researcher (edit me)"]
        assert "- Researcher\n" not in result.yaml
        assert not any("researchers" in str(e) for e in result.errors)


def test_a_researcher_name_that_is_set_is_left_alone():
    seed = {
        "protocolVersion": 4,
        "study": {"id": "draft", "researchers": ["Dr Ada Lovelace"]},
        "researchQuestions": [{"id": "RQ-1", "text": "Q?"}],
        "phases": [{"name": "design", "gates": []}],
    }
    result = compiler.compile_moves([], base_yaml=yaml.safe_dump(seed))
    assert result.draft["study"]["researchers"] == ["Dr Ada Lovelace"]


def test_researcher_conditions_replace_template_placeholder_conditions():
    # The design assistant chooses a template with no parameters and names the
    # conditions in a separate move. The template's placeholders
    # (control/treatment) must give way to them, not sit beside them: a
    # two-group study has exactly two conditions.
    conditions = {
        "moveId": "m-cond",
        "kind": "set-parameter",
        "target": "conditions[]",
        "proposal": "Compare AI-assisted work with unassisted work.",
        "patch": {
            "section": "conditions",
            "op": "append",
            "value": ["ai-assisted", "unassisted"],
        },
        "grounding": [],
        "status": "accepted",
    }
    result = compiler.compile_moves(
        [_template_move("m-t", "two-group-rct-v1", {}), conditions, _rq_move()]
    )
    assert result.valid, result.errors
    assert yaml.safe_load(result.yaml)["conditions"] == ["ai-assisted", "unassisted"]
