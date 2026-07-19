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

// DropdownMenuSeparator: the hairline rules dividing groups of actions.
export function SeparatedMenu() {
  return (
    <DropdownMenu defaultOpen>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">Study actions</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Context-Ablation 2026</DropdownMenuLabel>
        <DropdownMenuItem>Open protocol</DropdownMenuItem>
        <DropdownMenuItem>Duplicate study</DropdownMenuItem>
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
