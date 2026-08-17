import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SourceTimeline } from "./SourceTimeline";

const SEGMENTS = [
  { id: "a", start: 0, end: 60, selected: true, title: "Arranque", score: 92 },
  { id: "b", start: 300, end: 360, selected: false, title: "Medio", score: 40 },
];

describe("SourceTimeline", () => {
  it("ubica cada momento donde cae dentro del video", () => {
    const { container } = render(<SourceTimeline duration={600} segments={SEGMENTS} />);

    const marks = container.querySelectorAll(".timeline__segment");
    expect(marks).toHaveLength(2);
    expect((marks[0] as HTMLElement).style.left).toBe("0%");
    expect((marks[0] as HTMLElement).style.width).toBe("10%");
    expect((marks[1] as HTMLElement).style.left).toBe("50%");
  });

  it("distingue los elegidos de los descartados", () => {
    const { container } = render(<SourceTimeline duration={600} segments={SEGMENTS} />);

    expect(container.querySelectorAll(".is-selected")).toHaveLength(1);
    expect(container.querySelectorAll(".is-discarded")).toHaveLength(1);
  });

  it("recorta lo que se pasa del final del video", () => {
    const { container } = render(
      <SourceTimeline
        duration={100}
        segments={[{ id: "a", start: 50, end: 500, selected: true }]}
      />,
    );

    expect((container.querySelector(".timeline__segment") as HTMLElement).style.width).toBe(
      "50%",
    );
  });

  it("no divide por cero cuando todavía no sabemos la duración", () => {
    const { container } = render(
      <SourceTimeline duration={0} segments={[{ id: "a", start: 0, end: 10, selected: true }]} />,
    );

    expect(container.querySelector(".timeline__segment")).toBeInTheDocument();
  });

  it("es navegable con teclado cuando se puede elegir un momento", async () => {
    const onSelect = vi.fn();
    render(<SourceTimeline duration={600} segments={SEGMENTS} onSelect={onSelect} />);

    await userEvent.click(screen.getByRole("button", { name: /Arranque — 92 puntos/ }));

    expect(onSelect).toHaveBeenCalledWith("a");
  });
});
