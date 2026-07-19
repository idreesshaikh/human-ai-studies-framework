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

// DropdownMenuCheckItem: toggle rows with a leading check when enabled.
export function CheckItems() {
  return (
    <DropdownMenu defaultOpen>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">View options</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Conversation filters</DropdownMenuLabel>
        <DropdownMenuCheckItem checked>Grounded moves</DropdownMenuCheckItem>
        <DropdownMenuCheckItem checked>Cautions</DropdownMenuCheckItem>
        <DropdownMenuCheckItem>Unsourced moves</DropdownMenuCheckItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Reset filters</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
