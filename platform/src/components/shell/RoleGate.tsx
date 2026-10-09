import type { ReactNode } from "react";
import { hasRole, type Capability, type Role } from "@/lib/capabilities.ts";

/* Visibility is UX; the server enforces permissions. While the role loads, use pendingFallback. */
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
