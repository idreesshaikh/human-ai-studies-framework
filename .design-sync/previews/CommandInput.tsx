import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "platform";

// CommandInput is the search field at the top of the palette.
const noop = () => {};

export function SearchField() {
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
        </CommandGroup>
        <CommandGroup heading="Participants">
          <CommandItem>P-07 · within-subjects · counterbalanced</CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
