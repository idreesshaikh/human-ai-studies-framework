import { Badge } from "@/components/ui/badge";

/* Marks a design move that carries no citation. Dashed amber, not red —
 * unsourced means "your call", not "wrong". */
export function UnsourcedLabel() {
  return <Badge variant="unsourced">unsourced: needs your judgment</Badge>;
}
