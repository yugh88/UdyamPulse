import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type Row,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, ArrowUpDown, Columns3, Download, Rows3, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Button } from "./button";
import { DropdownMenu, MenuCheckboxItem, MenuLabel } from "./overlays";
import { EmptyState, ErrorState, SkeletonRows } from "./states";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    /** Plain-text column name for the visibility menu and CSV header. */
    label?: string;
    align?: "left" | "right";
    /** Value written to CSV (defaults to the accessor value). */
    csv?: (row: TData) => string | number | null | undefined;
  }
}

// Column value types vary per column, so the value generic is left open.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyColumn<T> = ColumnDef<T, any>;

const VIRTUALISE_ABOVE = 60;

export function toCsv(header: string[], rows: (string | number | null | undefined)[][]): string {
  const esc = (v: string | number | null | undefined) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [header, ...rows].map((r) => r.map(esc).join(",")).join("\n");
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export interface DataTableProps<T> {
  data: T[] | undefined;
  columns: AnyColumn<T>[];
  getRowId?: (row: T) => string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  emptyAction?: ReactNode;
  searchPlaceholder?: string;
  /** Extra controls rendered left of the search box (saved filters, bulk actions). */
  toolbar?: ReactNode;
  onRowClick?: (row: T) => void;
  rowLabel?: (row: T) => string;
  selectable?: boolean;
  onSelectionChange?: (rows: T[]) => void;
  csvName?: string;
  initialSort?: SortingState;
  /** Max height of the scroll area; the header stays sticky inside it. */
  maxHeight?: number;
  caption: string;
}

export function DataTable<T>({
  data,
  columns,
  getRowId,
  loading,
  error,
  onRetry,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  searchPlaceholder,
  toolbar,
  onRowClick,
  rowLabel,
  selectable,
  onSelectionChange,
  csvName,
  initialSort = [],
  maxHeight = 560,
  caption,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSort);
  const [globalFilter, setGlobalFilter] = useState("");
  const [visibility, setVisibility] = useState<VisibilityState>({});
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [compact, setCompact] = useState(() => localStorage.getItem("up_table_compact") === "1");

  const cols = useMemo<AnyColumn<T>[]>(() => {
    if (!selectable) return columns;
    const select: ColumnDef<T> = {
      id: "__select",
      enableSorting: false,
      enableHiding: false,
      header: ({ table }) => (
        <input
          type="checkbox"
          aria-label="Select all rows"
          className="h-4 w-4 accent-[var(--primary)]"
          checked={table.getIsAllRowsSelected()}
          ref={(el) => {
            if (el) el.indeterminate = table.getIsSomeRowsSelected();
          }}
          onChange={table.getToggleAllRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          aria-label="Select row"
          className="h-4 w-4 accent-[var(--primary)]"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    };
    return [select, ...columns];
  }, [columns, selectable]);

  const table = useReactTable({
    data: data ?? [],
    columns: cols,
    getRowId,
    state: { sorting, globalFilter, columnVisibility: visibility, rowSelection: selection },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setVisibility,
    onRowSelectionChange: setSelection,
    enableRowSelection: !!selectable,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const rows = table.getRowModel().rows;
  const selectedRows = table.getSelectedRowModel().rows;
  const onSel = useRef(onSelectionChange);
  onSel.current = onSelectionChange;
  useEffect(() => {
    onSel.current?.(selectedRows.map((r) => r.original));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection, data]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const rowHeight = compact ? 34 : 44;
  const virtual = rows.length > VIRTUALISE_ABOVE;
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 12,
    enabled: virtual,
  });
  const items = virtual ? virtualizer.getVirtualItems() : [];
  const padTop = virtual && items.length ? items[0].start : 0;
  const padBottom = virtual && items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0;
  const visibleRows: Row<T>[] = virtual ? items.map((v) => rows[v.index]) : rows;

  function exportCsv() {
    const leaf = table.getVisibleLeafColumns().filter((c) => c.id !== "__select");
    const header = leaf.map((c) => c.columnDef.meta?.label ?? (typeof c.columnDef.header === "string" ? c.columnDef.header : c.id));
    const body = rows.map((r) => leaf.map((c) => (c.columnDef.meta?.csv ? c.columnDef.meta.csv(r.original) : (r.getValue(c.id) as string | number | null))));
    download(`${csvName ?? "export"}.csv`, toCsv(header, body));
  }

  const hideable = table.getAllLeafColumns().filter((c) => c.getCanHide());
  const colCount = table.getVisibleLeafColumns().length;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 pb-3">
        {toolbar}
        <div className="ml-auto flex items-center gap-2">
          {searchPlaceholder && (
            <label className="relative block">
              <span className="sr-only">{searchPlaceholder}</span>
              <Search className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-fg-muted" aria-hidden />
              <input
                type="search"
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                placeholder={searchPlaceholder}
                className="h-8 w-56 rounded-control border border-edge-strong bg-panel pr-2 pl-8 text-13 text-fg placeholder:text-fg-subtle focus:border-primary"
              />
            </label>
          )}
          <DropdownMenu
            trigger={
              <Button size="sm" variant="ghost" aria-label="Choose columns" icon={<Columns3 className="h-4 w-4" aria-hidden />}>
                <span className="hidden lg:inline">Columns</span>
              </Button>
            }
          >
            <MenuLabel>Show columns</MenuLabel>
            {hideable.map((c) => (
              <MenuCheckboxItem key={c.id} checked={c.getIsVisible()} onCheckedChange={(v) => c.toggleVisibility(!!v)} onSelect={(e) => e.preventDefault()}>
                {c.columnDef.meta?.label ?? (typeof c.columnDef.header === "string" ? c.columnDef.header : c.id)}
              </MenuCheckboxItem>
            ))}
          </DropdownMenu>
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={compact}
            aria-label="Compact rows"
            onClick={() => {
              localStorage.setItem("up_table_compact", compact ? "0" : "1");
              setCompact(!compact);
            }}
            icon={<Rows3 className="h-4 w-4" aria-hidden />}
          >
            <span className="hidden lg:inline">Compact</span>
          </Button>
          {csvName && (
            <Button size="sm" variant="ghost" onClick={exportCsv} disabled={!rows.length} aria-label="Export CSV" icon={<Download className="h-4 w-4" aria-hidden />}>
              <span className="hidden lg:inline">CSV</span>
            </Button>
          )}
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : loading ? (
        <SkeletonRows rows={6} />
      ) : (
        <div ref={scrollRef} className="overflow-auto rounded-control border border-edge" style={{ maxHeight }}>
          <table className="w-full border-separate border-spacing-0 text-13">
            <caption className="sr-only">{caption}</caption>
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const sorted = h.column.getIsSorted();
                    const right = h.column.columnDef.meta?.align === "right";
                    return (
                      <th
                        key={h.id}
                        scope="col"
                        aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : h.column.getCanSort() ? "none" : undefined}
                        className={cn(
                          "sticky top-0 z-10 border-b border-edge bg-panel-2 px-3 py-2 text-xs font-medium whitespace-nowrap text-fg-muted",
                          right ? "text-right" : "text-left",
                        )}
                      >
                        {h.isPlaceholder ? null : h.column.getCanSort() ? (
                          <button
                            type="button"
                            onClick={h.column.getToggleSortingHandler()}
                            className={cn("inline-flex items-center gap-1 hover:text-fg", right && "flex-row-reverse")}
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            {sorted === "asc" ? (
                              <ArrowUp className="h-3 w-3" aria-hidden />
                            ) : sorted === "desc" ? (
                              <ArrowDown className="h-3 w-3" aria-hidden />
                            ) : (
                              <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden />
                            )}
                          </button>
                        ) : (
                          flexRender(h.column.columnDef.header, h.getContext())
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {padTop > 0 && (
                <tr aria-hidden>
                  <td colSpan={colCount} style={{ height: padTop }} />
                </tr>
              )}
              {visibleRows.map((row) => (
                <tr
                  key={row.id}
                  style={{ height: rowHeight }}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={onRowClick && rowLabel ? rowLabel(row.original) : undefined}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" && e.target === e.currentTarget) onRowClick(row.original);
                        }
                      : undefined
                  }
                  className={cn("bg-panel transition-colors", onRowClick && "cursor-pointer hover:bg-panel-2", row.getIsSelected() && "bg-primary-tint hover:bg-primary-tint")}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cn("border-b border-edge px-3 text-fg", compact ? "py-1" : "py-2", cell.column.columnDef.meta?.align === "right" && "tabular text-right")}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
              {padBottom > 0 && (
                <tr aria-hidden>
                  <td colSpan={colCount} style={{ height: padBottom }} />
                </tr>
              )}
            </tbody>
          </table>
          {rows.length === 0 && (
            <EmptyState
              title={globalFilter ? "No matches" : emptyTitle}
              description={globalFilter ? `Nothing matches “${globalFilter}”.` : emptyDescription}
              action={globalFilter ? <Button onClick={() => setGlobalFilter("")}>Clear search</Button> : emptyAction}
            />
          )}
        </div>
      )}
      {!loading && !error && (
        <p className="tabular pt-2 text-xs text-fg-muted" aria-live="polite">
          {rows.length} {rows.length === 1 ? "row" : "rows"}
          {data && rows.length !== data.length ? ` of ${data.length}` : ""}
          {selectedRows.length > 0 ? ` · ${selectedRows.length} selected` : ""}
        </p>
      )}
    </div>
  );
}
