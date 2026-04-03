import { cn } from "@/lib/cn";
import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes, HTMLAttributes } from "react";

/* ─── Root ─────────────────────────────────────────────────────────── */

type TableProps = HTMLAttributes<HTMLTableElement> & {
  children: ReactNode;
};

export function Table({ className, children, ...props }: TableProps) {
  return (
    <div className="ds-table-wrap" role="region" tabIndex={0}>
      <table className={cn("ds-table", className)} {...props}>
        {children}
      </table>
    </div>
  );
}

/* ─── Sections ─────────────────────────────────────────────────────── */

export function TableHeader({ className, children, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn("ds-table__head", className)} {...props}>
      {children}
    </thead>
  );
}

export function TableBody({ className, children, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={cn("ds-table__body", className)} {...props}>
      {children}
    </tbody>
  );
}

/* ─── Row ──────────────────────────────────────────────────────────── */

type TableRowProps = HTMLAttributes<HTMLTableRowElement> & {
  selected?: boolean;
};

export function TableRow({ className, selected, children, ...props }: TableRowProps) {
  return (
    <tr
      aria-selected={selected}
      className={cn("ds-table__row", selected && "ds-table__row--selected", className)}
      {...props}
    >
      {children}
    </tr>
  );
}

/* ─── Cells ────────────────────────────────────────────────────────── */

type TableHeadCellProps = ThHTMLAttributes<HTMLTableCellElement> & {
  sortable?: boolean;
  sorted?: "asc" | "desc" | false;
};

export function TableHeadCell({
  className,
  sortable,
  sorted,
  children,
  ...props
}: TableHeadCellProps) {
  return (
    <th
      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
      className={cn("ds-table__th", sortable && "ds-table__th--sortable", className)}
      scope="col"
      {...props}
    >
      {children}
      {sortable ? (
        <span aria-hidden="true" className="ds-table__sort-icon">
          {sorted === "asc" ? "↑" : sorted === "desc" ? "↓" : "↕"}
        </span>
      ) : null}
    </th>
  );
}

export function TableCell({ className, children, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("ds-table__td", className)} {...props}>
      {children}
    </td>
  );
}

/* ─── Empty State ──────────────────────────────────────────────────── */

export function TableEmpty({
  colSpan,
  message = "Nenhum registro encontrado.",
}: {
  colSpan: number;
  message?: string;
}) {
  return (
    <tr>
      <td className="ds-table__empty" colSpan={colSpan}>
        {message}
      </td>
    </tr>
  );
}
