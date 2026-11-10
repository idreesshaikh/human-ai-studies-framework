import { Button } from "./button";

export function paginate<T>(rows: T[], page: number, pageSize = 6) {
  const current = Math.max(0, Math.min(page, Math.ceil(rows.length / pageSize) - 1));
  return { rows: rows.slice(current * pageSize, (current + 1) * pageSize), page: current, pageSize, total: rows.length };
}

export function Pagination({ page, pageSize, total, label, onChange }: {
  page: number;
  pageSize: number;
  total: number;
  label: string;
  onChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;
  return (
    <nav aria-label={`${label} pages`} className="flex flex-wrap items-center justify-between gap-3 pt-3">
      <p className="type-note tabular text-text-muted" role="status">
        {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
      </p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" aria-label={`Previous ${label.toLowerCase()} page`} disabled={page === 0} onClick={() => onChange(page - 1)}>Previous</Button>
        <Button size="sm" variant="outline" aria-label={`Next ${label.toLowerCase()} page`} disabled={(page + 1) * pageSize >= total} onClick={() => onChange(page + 1)}>Next</Button>
      </div>
    </nav>
  );
}
