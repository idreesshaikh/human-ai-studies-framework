# Plan

The **Plan** tab estimates how many participants the analysis in your protocol
needs. Every number on it follows from assumptions you enter, and the tab shows
them next to the result.

<figure markdown="span">
  ![The Plan tab with the recorded design, the outcome measure and the planned test](../assets/screens/plan-light.webp#only-light)
  ![The Plan tab with the recorded design, the outcome measure and the planned test](../assets/screens/plan-dark.webp#only-dark)
  <figcaption>Plan for the example study. A warning at the top flags that the protocol does not yet say how AI access is controlled in each condition.</figcaption>
</figure>

## Estimate recruitment

The tab reads the design, the outcome and the planned test from the protocol.
To change them, change the protocol on **Setup**. You enter:

- the outcome's distribution;
- the effect to detect, in the outcome's units, and its spread;
- the two-sided alpha and the target power;
- the share of participants you expect to drop out.

t-tests and ANCOVA are computed directly; rank tests are simulated with a fixed
seed. When a combination is not supported, the tab says why instead of showing
a number. The chart shows power with simulation intervals, and the sensitivity
view shows the smallest effect each planned sample size can detect.

Saving a plan pins it to the exact protocol it was made for. Real pilot
sessions tagged on [Data](data.md) can update the spread and show the
recruitment estimate before and after. A pilot with fewer than eight
participants is flagged.

## Outcomes

Manual entry and accepted catalogue suggestions create typed outcomes, each
with its capture fields, questionnaire definitions and compatible analysis
recipes. Editing a typed protocol keeps existing measurement IDs, scales,
wording and covariates. A custom outcome needs its collection and analysis
defined before it can be saved. Catalogue suggestions are matches for you to
confirm, not measured estimates of validity.

## AI access in control conditions

- A warning at the top of the tab appears when the protocol has control
  conditions but does not say whether each may use AI, how that is enforced,
  and how it is checked.
- **Non-compliance sensitivity** simulates what happens when some control
  participants use AI anyway, or some AI-condition participants do not: how far
  each analysis moves from the true effect, and how many participants each then
  needs. The rates are assumptions you set. StudyLoop cannot verify that a
  control condition stayed free of AI. The **Route mix** presets use measured
  rates and stay unavailable until TERN's calibration is finished.

The [planner guide](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/docs/planner.md)
covers effect units, covariate and period limits, protocol v6 instruments, the
API and its evaluation checks.
