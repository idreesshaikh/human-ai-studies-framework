import { Card, CardHeader, CardTitle, CardContent } from "platform";

export function TitleInCard() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Comprehension debt under AI assistance</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            A Masters study on how AI pair-programming shifts the cost of
            understanding onto later maintenance.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function TitleOnly() {
  return (
    <div style={{ maxWidth: 360 }}>
      <Card>
        <CardHeader>
          <CardTitle>Context-ablation 2026</CardTitle>
        </CardHeader>
      </Card>
    </div>
  );
}
