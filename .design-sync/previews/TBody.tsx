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
          <TD>P-04</TD>
          <TD>AI-assisted</TD>
          <TD className="tabular">3</TD>
          <TD>
            <Badge variant="grounded">complete</Badge>
          </TD>
        </TR>
        <TR>
          <TD>P-05</TD>
          <TD>Control</TD>
          <TD className="tabular">2</TD>
          <TD>
            <Badge variant="outline">in progress</Badge>
          </TD>
        </TR>
        <TR>
          <TD>P-06</TD>
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

export function MoveLedger() {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Design move</TH>
          <TH>Provenance</TH>
          <TH>Decision</TH>
        </TR>
      </THead>
      <TBody>
        <TR>
          <TD>Counterbalance task order</TD>
          <TD>
            <Badge variant="grounded">grounded</Badge>
          </TD>
          <TD>accepted</TD>
        </TR>
        <TR>
          <TD>Add think-aloud protocol</TD>
          <TD>
            <Badge variant="unsourced">unsourced</Badge>
          </TD>
          <TD>rejected</TD>
        </TR>
      </TBody>
    </Table>
  );
}
