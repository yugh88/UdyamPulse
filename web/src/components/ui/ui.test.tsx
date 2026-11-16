import type { ColumnDef } from "@tanstack/react-table";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BandPill, Button, DataTable, ErrorState, Field, Input, ScoreGauge, SeverityPill, Stat, Stepper, toCsv } from ".";

describe("BandPill and SeverityPill", () => {
  it("shows a text label and an icon, not colour alone", () => {
    const { container } = render(
      <>
        <BandPill band="APPROVE" />
        <BandPill band="WATCH" />
        <BandPill band="HIGH_RISK" />
        <SeverityPill severity="high" />
      </>,
    );
    for (const label of ["Approve", "Watch", "High risk", "High"]) expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelectorAll("svg")).toHaveLength(4);
  });
  it("renders a dash when there is no band", () => {
    render(<BandPill band={null} />);
    expect(screen.getByText("–")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("is disabled and busy while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Approve
      </Button>,
    );
    const b = screen.getByRole("button", { name: "Approve" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Field", () => {
  it("links the label and the validation message to the control", () => {
    render(
      <Field label="Comment" error="A comment is required" required>
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText(/Comment/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("A comment is required");
    expect(screen.getByRole("alert")).toHaveTextContent("A comment is required");
  });
});

describe("ScoreGauge", () => {
  it("announces the score and band", () => {
    render(<ScoreGauge score={723} band="APPROVE" />);
    expect(screen.getByRole("img", { name: "Factory Health Score 723 out of 900, band Approve" })).toBeInTheDocument();
  });
  it("handles an unscored application", () => {
    render(<ScoreGauge score={null} />);
    expect(screen.getByRole("img", { name: "Factory Health Score: not scored yet" })).toBeInTheDocument();
  });
});

describe("Stepper", () => {
  it("marks the current step", () => {
    render(<Stepper current="SCORED" />);
    const current = screen.getByText("Scored").closest("li");
    expect(current).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Applied").closest("li")).not.toHaveAttribute("aria-current");
  });
});

describe("Stat", () => {
  it("shows the trend direction in text as well as colour", () => {
    render(<Stat label="Average score" value="712" delta={-8} deltaLabel="−8 vs last month" />);
    expect(screen.getByText("−8 vs last month")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("offers a retry", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new Error("Network down")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Network down");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

interface Row {
  id: number;
  name: string;
  score: number;
}
const ROWS: Row[] = [
  { id: 1, name: "Sharma Auto Components", score: 723 },
  { id: 2, name: "Morbi Ceramics", score: 590 },
  { id: 3, name: "Tiruppur Knits", score: 810 },
];
const COLS: ColumnDef<Row>[] = [
  { accessorKey: "name", header: "Factory" },
  { accessorKey: "score", header: "Score", meta: { align: "right" } },
];

describe("DataTable", () => {
  it("sorts when a header is clicked (numbers start highest first)", async () => {
    render(<DataTable caption="Factories" data={ROWS} columns={COLS} getRowId={(r) => String(r.id)} />);
    const names = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(names()).toEqual(["Sharma Auto Components", "Morbi Ceramics", "Tiruppur Knits"]);
    await userEvent.click(screen.getByRole("button", { name: /Score/ }));
    expect(names()).toEqual(["Tiruppur Knits", "Sharma Auto Components", "Morbi Ceramics"]);
    expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute("aria-sort", "descending");
    await userEvent.click(screen.getByRole("button", { name: /Score/ }));
    expect(names()).toEqual(["Morbi Ceramics", "Sharma Auto Components", "Tiruppur Knits"]);
    expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute("aria-sort", "ascending");
  });

  it("filters with the search box and shows a clear-search empty state", async () => {
    render(<DataTable caption="Factories" data={ROWS} columns={COLS} searchPlaceholder="Search factories" />);
    await userEvent.type(screen.getByRole("searchbox"), "morbi");
    expect(screen.getAllByRole("row")).toHaveLength(2);
    await userEvent.clear(screen.getByRole("searchbox"));
    await userEvent.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText("No matches")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("shows loading, error and empty states", () => {
    const { rerender } = render(<DataTable caption="t" data={undefined} columns={COLS} loading />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    rerender(<DataTable caption="t" data={undefined} columns={COLS} error={new Error("boom")} onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    rerender(<DataTable caption="t" data={[]} columns={COLS} emptyTitle="No applications yet" />);
    expect(screen.getByText("No applications yet")).toBeInTheDocument();
  });

  it("opens a row with click or Enter", async () => {
    const open = vi.fn();
    render(<DataTable caption="t" data={ROWS} columns={COLS} onRowClick={open} rowLabel={(r) => `Open ${r.name}`} />);
    await userEvent.click(screen.getByText("Morbi Ceramics"));
    expect(open).toHaveBeenCalledWith(ROWS[1]);
    screen.getByRole("row", { name: "Open Tiruppur Knits" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(open).toHaveBeenLastCalledWith(ROWS[2]);
  });

  it("reports selected rows", async () => {
    const onSel = vi.fn();
    render(<DataTable caption="t" data={ROWS} columns={COLS} selectable onSelectionChange={onSel} getRowId={(r) => String(r.id)} />);
    await userEvent.click(screen.getAllByRole("checkbox", { name: "Select row" })[0]);
    expect(onSel).toHaveBeenLastCalledWith([ROWS[0]]);
    await userEvent.click(screen.getByRole("checkbox", { name: "Select all rows" }));
    expect(onSel).toHaveBeenLastCalledWith(ROWS);
  });
});

describe("toCsv", () => {
  it("quotes commas, quotes and newlines", () => {
    expect(
      toCsv(
        ["a", "b"],
        [
          ["x,y", 'say "hi"'],
          [1, null],
        ],
      ),
    ).toBe('a,b\n"x,y","say ""hi"""\n1,');
  });
});
