# Start a study

Build the platform and run the server as described in the [repository README](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/README.md). Open the researcher workspace and create a study in your project. Record the protocol in Setup, estimate recruitment in Plan, connect participants in Run, and inspect captures and inclusion decisions in Data.

The [planner guide](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/planner.md) describes protocol v6, typed surveys, pilot updates, and control-arm audit limits. No demo or rehearsal sessions are inserted automatically. Auth configuration remains available.

## Try the populated example

After building, run this from the repository root:

```bash
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000> and choose **Example: Copilot and bug fixing
(synthetic data)**. Inspect the protocol, plan, illustrative links and simulated
sessions. The launcher uses temporary storage and disables live model calls;
use manual entry to demonstrate a new protocol. All rehearsal changes disappear
when it stops. Example links cannot connect an editor.

See the [showcase walkthrough](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/demo-walkthrough.md)
for the presentation script and fallback route.
