import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "platform";

// CommandEmpty renders only when nothing matches the search. Passing a
// controlled `value` that matches none of the items forces that state honestly.
const noop = () => {};

export function NoResults() {
  return (
    <CommandDialog
      open={true}
      onOpenChange={noop}
      label="Search the study workspace"
    >
      <CommandInput
        value="qzzx unmatched query"
        onValueChange={noop}
        placeholder="Search papers, participants, and moves…"
      />
      <CommandList>
        <CommandEmpty>No matches in the corpus or roster.</CommandEmpty>
        <CommandGroup heading="Papers">
          <CommandItem>Trust in AI Code Generation · 2024</CommandItem>
          <CommandItem>Comprehension Debt in AI-Assisted Programming · 2025</CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
