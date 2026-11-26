# Non-compliance sensitivity

Some control participants may use AI anyway, and some AI-condition participants
may not. **Non-compliance sensitivity**, at the foot of the **Plan** tab, simulates
how far that moves each analysis from the true effect of using AI, and how many
participants each analysis then needs. The rates are assumptions you set. The
simulation reads nothing from your study data, and StudyLoop cannot verify that a
control condition stayed free of AI.

## Run a simulation

Fill in the fields and choose **Run simulation**.

| Field | What it sets |
| --- | --- |
| **Effect of using AI** | The change AI causes in the outcome, in standard-deviation units |
| **Participants per arm** | 4 to 1000 |
| **Control-arm violation rate** | The share of the control arm who use AI anyway, up to 0.5 |
| **AI-arm non-use rate** | The share of the AI arm who do not use it |
| **Who breaks the condition** | **Random**, or **Skill-linked**: the weakest controls violate and the strongest AI-arm participants skip AI |
| **Telemetry flag rates** | The error rates of the telemetry flag: **Enter rates**, or one of two **Route mix** options |
| **Sensitivity** and **Specificity** | The share of real AI users the telemetry flags, and the share of non-users it correctly leaves unflagged |

!!! warning "TERN's flag rates have not been measured"
    The **Route mix** options use rates from TERN's calibration. That calibration
    has not produced measured rates yet, so the planner refuses a route mix.
    Enter the sensitivity and specificity you want to test under **Enter rates**.
    They are your assumptions, and the table says so beside its results.

## Read the table

**Simulated estimates by analysis** compares three ways of analysing the same
simulated studies:

| Analysis | What it compares |
| --- | --- |
| **As assigned** | The arms as randomised |
| **Drop flagged controls** | The arms after removing control participants flagged as AI users |
| **Flagged users against others** | People flagged as AI users against everyone else, across both arms |

For each one the table gives the bias (the average estimate minus the true
effect), the coverage of the 95% interval, how often the test rejects "no
difference", and the number of participants per arm needed to reject it in 80% of
simulated studies. The last analysis has no required sample size. The same inputs
always give the same table.

Rejecting "no difference" is not power to recover the true effect when an analysis
is biased. Use the table to choose an analysis and a recruitment margin, and plan
a contamination sensitivity analysis alongside it.

## Next steps

- [Create participant links](participants.md)
- [Control-arm session review](control-arm-review.md) for what the captured data shows
