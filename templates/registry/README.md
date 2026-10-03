# Study templates

The registry contains the feature-frozen set of generic study designs. A
template describes a design shape, its required instruments, its analysis
recipes, and the papers that support it. Instantiation produces a valid
protocol without hand-editing.

A template is not a paper replica. References provide evidence for the shape;
the deterministic repertoire ranks shapes by the number of matching papers.
Combining templates is supported, but the resulting protocol still needs
researcher review.

## Available designs

| Template | Design |
| --- | --- |
| `bounded-case-study-v1` | Bounded case study |
| `cognitive-load-comparison-v1` | Cognitive-load comparison |
| `factorial-2x2-v1` | 2×2 factorial |
| `field-experiment-v1` | Field experiment |
| `hai-eval-synergy-v1` | Human/AI/synergy comparison |
| `metr-rct-v1` | METR-style within-subjects RCT |
| `multi-arm-rct-v1` | Multi-arm RCT |
| `observational-field-v1` | Observational field study |
| `paired-pre-post-v1` | Paired pre/post intervention |
| `single-arm-benchmark-v1` | Single-arm benchmark |
| `single-group-repeated-measures-v1` | Repeated measures |
| `survey-self-report-v1` | Self-report only |
| `two-group-rct-v1` | Two-group RCT |
| `two-proportion-mcnemar-v1` | Two-proportion comparison |
| `within-subjects-crossover-v1` | Within-subjects crossover |
| `ziegler-telemetry-survey-v1` | Telemetry plus survey |

The registry is frozen with these 16 designs. Refinements must preserve the
template schema, citations, recipe compatibility, and generated protocol
validity. New design families are outside the release scope.

## Validation

`middleware/src/middleware/template_registry.py` checks schema shape,
mandatory citations, recipe names, and declared placeholders. It cannot decide
whether a recipe is methodologically appropriate for a particular question;
the researcher must make that judgment.

Drafts in [`templates/drafts`](../drafts/) are intentionally not registry
entries. They reference data paths or recipes that the supported live workflow
does not provide. Do not promote one without a complete, tested vertical slice.

Templates are library content. A study is a protocol instance in
`protocol/examples/` and may start from a template, but it is never itself a
template.
