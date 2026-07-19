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

// DropdownMenuLabel: the muted section heading atop the menu.
export function LabeledMenu() {
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
