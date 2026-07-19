import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuCheckItem,
  DropdownMenuSeparator,
  Button,
} from "platform";

// Radix DropdownMenu renders nothing until opened — defaultOpen forces the
// portalled menu to render so the whole panel is captured.
export function StudyActions() {
  return (
    <DropdownMenu defaultOpen>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">Study actions</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Context-Ablation 2026</DropdownMenuLabel>
        <DropdownMenuItem>Open protocol</DropdownMenuItem>
        <DropdownMenuItem>Duplicate study</DropdownMenuItem>
        <DropdownMenuItem>Export as YAML</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuCheckItem checked>
          Show unsourced moves
        </DropdownMenuCheckItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem destructive>Archive study</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
