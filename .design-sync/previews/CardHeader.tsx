import { Card, CardHeader, CardTitle, CardContent, Badge } from "platform";

export function HeaderWithTitle() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Design conversation</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            Twelve proposed moves, eight accepted, compiled into the protocol
            draft.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function HeaderWithBadge() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <CardTitle>Recall accuracy</CardTitle>
            <Badge variant="grounded">grounded</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            Prescribed statistic: Welch's t-test, two-tailed, α = .05.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
