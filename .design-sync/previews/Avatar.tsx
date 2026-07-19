import { Avatar } from "platform";

const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  flexWrap: "wrap",
};

const person: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: 13,
};

export function Initials() {
  return (
    <div style={row}>
      <Avatar name="Idrees Razak" />
      <Avatar name="Priya Nair" />
      <Avatar name="Marcus Feld" />
      <Avatar name="razakidrees@gmail.com" />
    </div>
  );
}

export function WithNames() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={person}>
        <Avatar name="Idrees Razak" />
        <span>Idrees Razak — principal investigator</span>
      </div>
      <div style={person}>
        <Avatar name="Priya Nair" />
        <span>Priya Nair — co-researcher</span>
      </div>
      <div style={person}>
        <Avatar name="Marcus Feld" />
        <span>Marcus Feld — analyst</span>
      </div>
    </div>
  );
}
