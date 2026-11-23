# Data

The **Data** tab shows every session TERN captured for the study, checks it for
gaps, and records your decision on whether each session counts. It is also
where you download the study's records.

<figure markdown="span">
  ![The Data tab with the download buttons, Check captured inputs, and synthetic sessions with their event counts](../assets/screens/data-light.webp#only-light)
  ![The Data tab with the download buttons, Check captured inputs, and synthetic sessions with their event counts](../assets/screens/data-dark.webp#only-dark)
  <figcaption>The example study's sessions are simulated and labelled as such. A real study shows only captured sessions here.</figcaption>
</figure>

## Download study records

| Button | What you get |
| --- | --- |
| **Data (.zip)** | Tidy event CSVs, joined JSON and a data dictionary. Synthetic rows are left out; pilot tags and inclusion decisions are kept |
| **Design card (.md)** | The saved power assumptions, the fixed analysis, instrument versions and wording, the tool and model each session used, audit results and inclusion decisions |
| **Replication kit** | The design card plus the frozen protocol, data and report |

The data bundle also contains the design card as JSON. Nothing in these files
rates the study's validity or pools repeated runs.

## Check outcome capture

After a rehearsal, **Check captured inputs** compares what was captured with
what each declared outcome needs: the instrument, the required fields, their
versions, condition coverage and participant pairs. Expand a result for what to
fix, and download the checks as JSON to keep the protocol and data fingerprints.

This checks inputs, not validity. Custom measures the checker does not know
stay unverified, and pilot sessions can be checked without changing their tags
or decisions.

## Review sessions

Search sessions by participant, condition or session ID. Each row shows its
event count, metric rows and gaps in the event sequence; expand it for its
timeline.

**Session review** starts with control sessions that need attention. Switch
**Show sessions** to **All sessions** to decide on any session. For each one
you can:

- **tag it as a pilot**, with a reason. Pilots stay in exports, marked, and are
  left out of confirmatory recipes and metric comparisons;
- **record an inclusion or exclusion decision.** Each decision keeps the date
  and its history. With sign-in off, the recorded identity is `local`.

## The control-arm audit

For sessions in a no-AI condition, the audit reports one of three outcomes:

| Shown as | Meaning |
| --- | --- |
| **No captured AI-use signal** | No signal in the captured data. This never proves no AI was used |
| **Captured AI-use signal** | A heuristic fired. It is a reason to look, not proof of AI use |
| **Capture needs review** | Capture boundaries or settings were missing, so the audit abstains |

!!! warning "Accuracy not yet measured"
    The audit's error rates have not been measured; independent scripted
    calibration sessions are required first. Until then, treat every outcome
    as a prompt for your own judgement. **Capture limits** on the tab lists
    what the audit cannot see: paste origins and AI edit classifications are
    heuristics, and command-line tools and activity outside the editor are
    not captured.

## Results

Once real sessions arrive, **Measurements by condition** compares the outcomes
across conditions, and **Recorded analysis plan** shows the analysis the
protocol fixed in advance.

The [planner guide](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/planner.md)
covers pilot updates, numerical limits and how the audit will be calibrated.
