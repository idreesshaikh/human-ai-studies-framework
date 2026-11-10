# Example walkthrough

After [installation and build](../README.md#run-locally), run:

```bash
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. The launcher uses temporary storage, disables
live model calls, and removes rehearsal data on Ctrl+C. Add `--port 8001` if
needed. Downloaded exports remain in your download folder.

## Explore the workflow

1. Open **Example: Copilot and bug fixing (synthetic data)**. Inspect its
   approved protocol and saved recruitment plan.
2. In **Run**, inspect assignment and capture scope. The 24 example links are
   illustrative and cannot connect an editor.
3. In **Data**, inspect the 25 simulated sessions, including incomplete capture,
   sequence gaps, and control-arm signals.
   Select **Check captured inputs** and expand an outcome to trace its declared
   fields to observed coverage, missing inputs, and corrective actions.
   Download the JSON checks to retain the protocol and data fingerprints.
4. Download a data bundle and design card. Default research exports exclude
   simulated observations.
5. Create a separate study and use manual protocol entry. Review and apply the
   compiled draft, then inspect its plan.

Example inputs for manual entry:

- Question: Does Copilot change time to the first passing test on Java bug fixes?
- Design: within subjects; conditions `without AI` and `with Copilot`.
- Participants: professional Java developers; 24 planned participants.
- Task: fix two matched bugs in a Java service with a supplied test suite.
- Session: 45 minutes, with counterbalanced condition order.
- Outcomes: time to first green and overall workload from the measure catalog.

The count and duration are illustrative assumptions, not a justified sample
or observed Copilot effect. A paired comparison does not model every period
or carryover effect; see [planning limits](planner.md).

For live editor capture, create a separate study and follow the
[TERN setup](../extension/README.md). The seeded links cannot be used for it.
