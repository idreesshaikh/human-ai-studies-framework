# Check outcome capture

Before you rely on a rehearsal or a pilot, check that the data you captured can
answer your outcomes. **Outcome capture checks** compares what was captured with
what each outcome in your protocol needs: its instrument, its required fields and
versions, condition coverage and participant pairs. It checks inputs. It does not
check that a measure is valid.

## Run the check

1. Open the **Data** tab and expand **Outcome capture checks**.
2. Choose **Check captured inputs**. It reports how many sessions it checked,
   including pilots.
3. Expand an outcome to see its instrument and fields, how many session units have
   observed inputs, its analysis method, the participants per condition and the
   complete participant pairs. Each issue says what to fix and lists example
   sessions.
4. Choose **Download checks (.json)** to keep the report with the protocol and data
   fingerprints it was run against. **Check again** reruns it after you fix
   something.

## Reading the status

| Status | Meaning |
| --- | --- |
| **Inputs observed** | Every checked session has the inputs and no issue was raised |
| **Review coverage** | Every checked session has the inputs, but an issue needs a look, such as a condition with no inputs, no participant observed in both conditions, or a participant in both between-subjects conditions |
| **Partial outcome coverage** | Some checked sessions have the inputs and others do not |
| **No usable inputs** | No checked session has the inputs |
| **No sessions checked** | There are no sessions to check yet |
| **Custom check needed** | The checker does not know this measure, so its coverage stays unverified |
| **Configuration needs attention** | The outcome's instrument or capture is not configured in the protocol |

**Scope and provenance** at the foot of the report states what the check covers
and its limits. Pilot sessions are checked without changing their tags or your
decisions. The check never changes the protocol or any record.

Coverage does not establish construct validity, the quality of a test suite, or
that a statistical model suits the data, including carryover in paired designs.

## Next steps

- [Review sessions and export](data.md)
- [Control-arm session review](control-arm-review.md)
