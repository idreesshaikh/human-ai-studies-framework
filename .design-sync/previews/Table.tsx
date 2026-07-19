import { Table, THead, TBody, TR, TH, TD, Badge } from "platform";

// A realistic study roster — the precise register: hairline rules, tabular
// numerals, no motion. Content is study-domain (participants × condition).
export function ParticipantRoster() {
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
        <TR>
          <TD>P-03</TD>
          <TD>AI-assisted</TD>
          <TD className="tabular">1</TD>
          <TD>
            <Badge variant="unsourced">consent pending</Badge>
          </TD>
        </TR>
      </TBody>
    </Table>
  );
}
