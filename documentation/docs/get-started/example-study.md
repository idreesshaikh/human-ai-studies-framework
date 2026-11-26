# Explore the example study

The example is a finished study you can read tab by tab before you design your
own. It is a within-subjects comparison of debugging with and without Copilot,
with a saved recruitment plan, 24 participant links and 25 simulated sessions.
Every session is synthetic, so nothing in it is a finding.

Start it with [Install and run](index.md), then open **Example: Copilot and bug fixing (synthetic data)** on the **Studies** page.

## What to look at

| Tab | What the example shows |
| --- | --- |
| **Setup** | The applied protocol beside a short design conversation: two research questions, a within-subjects design, 24 planned participants, two conditions and the outcome measures. In the conversation, the assistant asks one decision at a time, and its last reply holds one card that proposes 30 participants instead of 24. **Review draft** shows the compiled protocol |
| **Literature** | An empty collection: the example holds no papers. Adding one by arXiv or DOI link makes a request to Semantic Scholar; see [Literature](../platform/library.md) |
| **Plan** | A saved recruitment plan with its assumptions and sensitivity table. See [Plan recruitment](../platform/planning.md) |
| **Run** | The 24 links, each with its condition, status and capture settings. They are illustrative and cannot connect an editor, and **Create participant links** is off for this study |
| **Data** | The 25 simulated sessions, including incomplete capture, sequence gaps and control-arm signals, under a notice that says they are synthetic |

!!! warning "Example data is not a finding"
    The rows are marked synthetic and are left out of data bundles, pilot
    estimates and analysis recipes. The example bundle includes the protocol,
    design card and data dictionary, with zero observation rows.

## Things to try

1. On **Data**, open **Outcome capture checks**, choose **Check captured inputs**
   and expand an outcome to trace its declared fields to observed coverage and
   missing inputs. See [Check outcome capture](../platform/outcome-checks.md).
2. Open a session, then its timeline, to see where events are missing. See
   [Review sessions and export](../platform/data.md).
3. Open **Session review** and read why a control session was flagged. See
   [Control-arm session review](../platform/control-arm-review.md).
4. Create a separate study and [enter the protocol details directly](../platform/manual-entry.md)
   to see how the compiled draft is reviewed and applied.

The repository also has a [presenter script](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/demo-walkthrough.md)
with sample inputs for the last step. To capture real data from an editor, create
a separate study: the example's links cannot be used.

## Next steps

- [Your first study](first-study.md)
- [Design a study](../platform/index.md)
