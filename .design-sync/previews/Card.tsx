import { Card, CardHeader, CardTitle, CardContent, Badge } from "platform";

export function StudyCard() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Comprehension debt under AI assistance</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 13, color: "inherit", lineHeight: 1.5 }}>
            Between-subjects design comparing AI-assisted and Control
            developers on delayed comprehension recall across 24 sessions.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function MoveCard() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Counterbalance task order</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
            }}
          >
            <Badge variant="grounded">grounded</Badge>
            <span>Latin-square ordering across four tasks.</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function CardGrid() {
  return (
    <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
      <Card>
        <CardHeader>
          <CardTitle>Participants</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 22, fontWeight: 600 }}>24</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Sessions logged</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 22, fontWeight: 600 }}>61</div>
        </CardContent>
      </Card>
    </div>
  );
}
