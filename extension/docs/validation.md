# Validation harness

`npm run validate` replays scripted scenarios through the edit-origin
classifier (`BurstAggregator`) and the `StuckDetector` on a mocked clock and
prints a report. Code lives in `test/validation/`; `validation.test.ts` is
the regression gate (runs under `npm test`).

> Scripted scenarios characterise rule behaviour and known failure modes
> against the signals as modelled here; they are NOT an accuracy estimate for
> real developer sessions.

Scenarios that the rules are expected to get wrong are flagged
(`knownFailure` / `knownFalseAlarm`) and listed in the report. The gate fails
if an unflagged scenario misbehaves, or if a flagged one starts passing.

## Optional: labelled real-session recording

`npm run validate -- --recording session.json` adds a separate section for a
recording. No real numbers are shipped with the repo.

```json
{
  "version": 1,
  "source": "vscode + <inline-suggestion tool>",
  "events": [
    {
      "t": 0,
      "kind": "change",
      "charsAdded": 1,
      "charsDeleted": 0,
      "lines": 1
    },
    { "t": 5000, "kind": "paste" },
    { "t": 5000, "kind": "change", "charsAdded": 120, "lines": 4 },
    { "t": 9000, "kind": "aiAccept" },
    { "t": 9000, "kind": "change", "charsAdded": 40 }
  ],
  "labels": ["human", "paste", "ai"]
}
```

- `events`: the exported signal log, `t` in ms from the first event,
  non-decreasing. `change` may also carry `fileKey` and `undoRedo`.
  `aiAccept` and `paste` are stamped when the adapter stamps them, i.e. at the
  first change after the command. Contents of the text are never recorded.
- `labels`: one human label per resulting burst, in order: `human`, `ai`,
  `paste` or `undo-redo`. The replay fails loudly if the burst count differs.
  Keep actions more than 2.5 s apart so each one is its own burst.

### Recording protocol

In real VS Code with an inline-suggestion tool installed and the extension
logging signals, a person performs each labelled action separately (about
3 s apart) and notes it as they go:

1. type a few lines by hand (`human`)
2. paste via keybinding (`paste`)
3. accept an inline suggestion (`ai`)
4. paste via the context menu (`paste`: expected to be mislabelled by the rules)
5. undo and redo (`undo-redo`)

Export the signal log, write the labels in the order the bursts occurred, and
pass the file to `--recording`.
