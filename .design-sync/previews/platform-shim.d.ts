// Ambient shim — IDE-only. The bare specifier "platform" that every preview
// imports is provided by the design-sync converter at build time (synth-entry
// mode; see .design-sync/NOTES.md), NOT by the repo's own TypeScript —
// platform/tsconfig.app.json compiles only src/, and platform/package.json
// declares no entry point, so tsc has nothing to resolve "platform" to.
// Without this, an editor opening a preview reports "Cannot find module
// 'platform'" (TS2307). This file is not a .tsx preview, so the design-sync
// converter's glob skips it, and no build references this directory.
//
// One full ambient block (the shorthand `declare module "platform";` can't
// merge with the type aliases below): component/value exports are `any`; the
// four types the previews use in type position alias to their real definitions
// so they resolve as types, not namespaces (TS2709).
//
// The value list mirrors every name the previews import — regenerate if a new
// preview pulls in a component this list doesn't have (TS2305 will point at it):
//   perl -0777 -ne 'while(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+"platform"/gs){...}' .design-sync/previews/*.tsx
// Some editors' TS servers resolve react/jsx-runtime to its .js but miss the
// @types/react declaration from platform/node_modules (TS7016), even though the
// CLI tsc finds it. Scoped to this preview-only program, this makes the JSX
// runtime `any` and clears the hint; the real app is unaffected (it compiles
// under platform/tsconfig.app.json, which resolves react's types normally).
declare module "react/jsx-runtime";

declare module "platform" {
  // Components, providers, and re-exported router primitives — used as values.
  export const AmendmentBanner: any;
  export const AmendmentHistory: any;
  export const Avatar: any;
  export const Badge: any;
  export const Button: any;
  export const Card: any;
  export const CardContent: any;
  export const CardHeader: any;
  export const CardTitle: any;
  export const CommandDialog: any;
  export const CommandEmpty: any;
  export const CommandGroup: any;
  export const CommandInput: any;
  export const CommandItem: any;
  export const CommandList: any;
  export const ConversationView: any;
  export const Dialog: any;
  export const DialogClose: any;
  export const DialogContent: any;
  export const DialogDescription: any;
  export const DialogTitle: any;
  export const DialogTrigger: any;
  export const DraftRail: any;
  export const DropdownMenu: any;
  export const DropdownMenuCheckItem: any;
  export const DropdownMenuContent: any;
  export const DropdownMenuItem: any;
  export const DropdownMenuLabel: any;
  export const DropdownMenuSeparator: any;
  export const DropdownMenuTrigger: any;
  export const EmptyState: any;
  export const FeedbackAffordance: any;
  export const GroundingChip: any;
  export const Input: any;
  export const Label: any;
  export const MemoryRouter: any;
  export const MoveCard: any;
  export const ProjectSwitcher: any;
  export const RecommendationCard: any;
  export const RoleGate: any;
  export const SlotMeter: any;
  export const StreamingTurn: any;
  export const TBody: any;
  export const TD: any;
  export const TH: any;
  export const THead: any;
  export const TR: any;
  export const Table: any;
  export const TierBadge: any;
  export const UnsourcedLabel: any;
  export const VersionChip: any;

  // The real types the previews import in type position.
  export type Amendment = import("../../platform/src/lib/types").Amendment;
  export type AmendmentState = import("../../platform/src/lib/types").AmendmentState;
  export type ProtocolDraft = import("../../platform/src/lib/types").ProtocolDraft;
  export type Turn = import("../../platform/src/lib/types").Turn;
}
