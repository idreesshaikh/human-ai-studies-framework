import { Card, CardHeader, CardTitle, CardContent, Badge } from "platform";

export function InCard() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Context-ablation 2026</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            Manipulates the retrieval window shown to the AI assistant and
            measures downstream defect density in the merged code.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function MixedContent() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Session P-07</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Condition</span>
              <span>AI-assisted</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Status</span>
              <Badge variant="grounded">complete</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
