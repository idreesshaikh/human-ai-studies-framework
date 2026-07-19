import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "platform";

// CommandDialog wraps the cmdk palette in a Radix dialog. Pass open + a no-op
// onOpenChange + a label so the portalled palette renders for capture.
const noop = () => {};

export function Palette() {
  return (
    <CommandDialog
      open={true}
      onOpenChange={noop}
      label="Search the study workspace"
    >
      <CommandInput placeholder="Search papers, participants, and moves…" />
      <CommandList>
        <CommandEmpty>No matches in the corpus or roster.</CommandEmpty>
        <CommandGroup heading="Papers">
          <CommandItem>Trust in AI Code Generation · 2024</CommandItem>
          <CommandItem>Comprehension Debt in AI-Assisted Programming · 2025</CommandItem>
          <CommandItem>Early-2025 AI Developer Productivity (METR) · 2025</CommandItem>
        </CommandGroup>
        <CommandGroup heading="Participants">
          <CommandItem>P-07 · within-subjects · counterbalanced</CommandItem>
          <CommandItem>P-12 · sample-study · session 3</CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
