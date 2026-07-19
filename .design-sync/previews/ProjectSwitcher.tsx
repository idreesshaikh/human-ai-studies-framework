import { ProjectSwitcher, MemoryRouter } from "platform";

// ProjectSwitcher is a ⌘K command palette; closed it renders its trigger
// chip. It calls useNavigate, so it must live inside a router. Memberships
// are realistic study projects with roles.
const memberships = [
  { projectSlug: "sample-lab", projectName: "Sample Lab", role: "owner" as const },
  {
    projectSlug: "sample-study",
    projectName: "Sample study",
    role: "researcher" as const,
  },
  {
    projectSlug: "demo",
    projectName: "Demo — AI code trust study",
    role: "viewer" as const,
  },
];

const frame: React.CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  padding: 16,
};

export function Trigger() {
  return (
    <MemoryRouter>
      <div style={frame}>
        <ProjectSwitcher memberships={memberships} />
      </div>
    </MemoryRouter>
  );
}
