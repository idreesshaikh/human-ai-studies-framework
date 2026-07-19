import { Table, THead, TBody, TR, TH, TD, Badge } from "platform";

export function InTable() {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Participant</TH>
          <TH>Condition</TH>
          <TH>Sessions</TH>
          <TH>Status</TH>
        </TR>
      </THead>
      <TBody>
        <TR>
          <TD>P-01</TD>
          <TD>AI-assisted</TD>
          <TD className="tabular">3</TD>
          <TD>
            <Badge variant="grounded">complete</Badge>
          </TD>
        </TR>
        <TR>
          <TD>P-02</TD>
          <TD>Control</TD>
          <TD className="tabular">2</TD>
          <TD>
            <Badge variant="outline">in progress</Badge>
          </TD>
        </TR>
      </TBody>
    </Table>
  );
}

export function MetricsHeader() {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Metric</TH>
          <TH>AI-assisted</TH>
          <TH>Control</TH>
        </TR>
      </THead>
      <TBody>
        <TR>
          <TD>Recall accuracy</TD>
          <TD className="tabular">0.71</TD>
          <TD className="tabular">0.83</TD>
        </TR>
        <TR>
          <TD>Time on task (min)</TD>
          <TD className="tabular">18.4</TD>
          <TD className="tabular">24.9</TD>
        </TR>
      </TBody>
    </Table>
  );
}
