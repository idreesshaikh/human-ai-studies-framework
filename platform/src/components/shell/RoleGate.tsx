import type { ReactNode } from "react";
import { hasRole, type Capability, type Role } from "@/lib/capabilities.ts";

/* Shows its children only when `role` can do `capability`. This is UX only
 * — hiding a control the server would refuse anyway. The server stays the
 * enforcement; this never guards data.
 *
 * `pending` is the third answer: the role hasn't loaded yet. Without it a
 * caller has to pick between "assume viewer" (the control flickers into
 * existence a beat later, or looks absent) and "assume owner" (a control
 * appears and then vanishes). Neither is honest, so while pending we render
 * `pendingFallback` — by default nothing, but a caller can pass a box of the
 * same size so the layout doesn't jump when the answer arrives. */
export function RoleGate({
  role,
  capability,
  children,
  fallback = null,
  pending = false,
  pendingFallback = null,
}: {
  role: Role | null | undefined;
  capability: Capability;
  children: ReactNode;
  fallback?: ReactNode;
  pending?: boolean;
  pendingFallback?: ReactNode;
}) {
  if (pending) return <>{pendingFallback}</>;
  return <>{hasRole(role, capability) ? children : fallback}</>;
}
