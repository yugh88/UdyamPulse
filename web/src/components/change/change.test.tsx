import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BeforeAfter, ChangeBadge, ChangedBar, Delta, WhatChanged, fmtValue } from ".";

describe("Delta", () => {
  it("is good when a good-when-up value rises, and says so in words", () => {
    render(<Delta value={25} goodWhenUp />);
    expect(screen.getByText("up 25, better")).toBeInTheDocument();
  });
  it("is direction-aware: a falling risk is good", () => {
    render(<Delta value={-2} goodWhenUp={false} suffix="since yesterday" />);
    expect(screen.getByText(/down 2, better/)).toBeInTheDocument();
  });
  it("shows relative change for money and points for shares", () => {
    render(
      <>
        <Delta before={142e5} after={84e5} unit="inr" />
        <Delta before={0.3} after={0.46} unit="share" goodWhenUp={false} />
      </>,
    );
    expect(screen.getByText("41%")).toBeInTheDocument();
    expect(screen.getByText("16 pts")).toBeInTheDocument();
    expect(screen.getByText(/up 16 pts, worse/)).toBeInTheDocument();
  });
  it("renders nothing without a change", () => {
    const { container } = render(<Delta value={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("BeforeAfter", () => {
  it("strikes the old value and bolds the new one", () => {
    render(<BeforeAfter before={723} after={641} />);
    expect(screen.getByText("723").closest("s")).not.toBeNull();
    expect(screen.getByText("641")).toBeInTheDocument();
    expect(screen.getByText(/down 82, worse/)).toBeInTheDocument();
  });
});

describe("change markers", () => {
  it("labels new and updated items in text, not colour alone", () => {
    render(
      <>
        <ChangeBadge kind="new" />
        <ChangeBadge kind="updated" />
        <ChangeBadge kind={null} />
      </>,
    );
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("Updated")).toBeInTheDocument();
    expect(screen.getAllByText(/changed since you last looked/)).toHaveLength(2);
  });
  it("draws the bar only when the item changed", () => {
    const { container } = render(<ChangedBar show={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("WhatChanged", () => {
  it("lists changes newest first with the actor and a New badge for unseen entries", () => {
    render(
      <WhatChanged
        items={[
          {
            id: 2,
            entity_type: "application",
            entity_id: "1",
            event_type: "scored",
            summary: "Scored 742: band Approve",
            before: { score: null },
            after: { score: 742 },
            actor: "rm1",
            created_at: new Date().toISOString(),
            new: true,
          },
          {
            id: 1,
            entity_type: "application",
            entity_id: "1",
            event_type: "opened",
            summary: "Application opened",
            before: null,
            after: null,
            actor: "rm1",
            created_at: new Date().toISOString(),
            new: false,
          },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Scored 742");
    expect(items[0]).toHaveTextContent("New");
    expect(items[0]).toHaveTextContent("by rm1");
    expect(items[1]).not.toHaveTextContent("New");
  });
  it("has an empty state", () => {
    render(<WhatChanged items={[]} />);
    expect(screen.getByText("Nothing has changed yet.")).toBeInTheDocument();
  });
});

describe("fmtValue", () => {
  it("formats rupees in lakh and crore, shares as percent, hours as minutes", () => {
    expect(fmtValue(45e5, "inr")).toBe("₹45.0 L");
    expect(fmtValue(1.1e7, "inr")).toBe("₹1.10 Cr");
    expect(fmtValue(0.46, "share")).toBe("46%");
    expect(fmtValue(0.13, "hours")).toBe("8 min");
  });
});
