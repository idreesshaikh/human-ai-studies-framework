import type { ReactNode } from "react";
import { hasRole, type Capability, type Role } from "@/lib/capabilities.ts";

/* Shows its children only when `role` can do `capability`. This is UX only
 * — hiding a control the server would refuse anyway. The server stays the
 * enforcement; this never guards data. */
export function RoleGate({
  role,
  capability,
  children,
  fallback = null,
}: {
  role: Role | null | undefined;
  capability: Capability;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return <>{hasRole(role, capability) ? children : fallback}</>;
}
