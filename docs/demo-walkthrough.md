# Example walkthrough

After the [quickstart](../README.md#quickstart) install and build, run:

```bash
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. The launcher uses temporary storage, disables
live model calls, and removes rehearsal data on Ctrl+C. Add `--port 8001` if
needed. Downloaded exports remain in your download folder.

To try the design chat in the same disposable setup, add `--live` and load your
model key, for example
`uv run --no-sync --env-file .env.local python scripts/run_demo.py --live`.
The chat then makes provider requests, and literature suggestions start once
the bundled paper corpus has loaded (about a minute).

## Explore the workflow

1. Open **Example: Copilot and bug fixing (synthetic data)**. Inspect its
   approved protocol and saved recruitment plan.
2. In **Run**, inspect assignment and capture scope. The 24 example links are
   illustrative and cannot connect an editor.
3. In **Data**, inspect the 25 simulated sessions, including incomplete capture,
   sequence gaps, and control-arm signals in **Session review**.
   Expand **Outcome capture checks**, select **Check captured inputs**, and expand
   **Time to first passing test** to show how many sessions recorded a usable
   time and why others did not. Download the JSON checks to retain the protocol
   and data fingerprints.
4. Download the data bundle or design card. The example bundle contains the
   protocol, design card and data dictionary, with zero observation rows.
5. Create a separate study and enter the protocol details directly. Review and
   apply the compiled draft, then inspect its plan.

Example inputs for manual entry:

- Question: Does Copilot change time to the first passing test on Java bug fixes?
- Design: within subjects; conditions `without AI` and `with Copilot`.
- Participants: professional Java developers; 24 planned participants.
- Tasks: add two entries, one for each matched bug in the same Java service.
  Each developer fixes one bug per condition using the supplied test suite.
- Session: 45 minutes, with counterbalanced condition order.
- Outcomes: **Time to first passing test** and **Workload (raw TLX)** from the measure catalog.

The count and duration are illustrative assumptions, not a justified sample
or observed Copilot effect. A paired comparison does not model every period
or carryover effect; see [planning limits](planner.md).

For live editor capture, create a separate study and follow the
[TERN setup](../extension/README.md). The seeded links cannot be used for it.
The [user guide](../documentation/docs/get-started/example-study.md) explains each
tab of the example for readers who are not presenting it.
