import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "platform";

// CommandList is the scrollable results region holding groups and items.
const noop = () => {};

export function Results() {
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
        <CommandGroup heading="Design moves">
          <CommandItem>Add code-verification measure</CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
