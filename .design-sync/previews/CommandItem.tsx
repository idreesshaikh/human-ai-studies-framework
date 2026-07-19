import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "platform";

// CommandItem: a single selectable result row (the first is highlighted).
const noop = () => {};

export function Items() {
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
      </CommandList>
    </CommandDialog>
  );
}
