import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TrimTrack } from "./TrimTrack";

const base = {
  duration: 100,
  start: 20,
  end: 60,
  playhead: 35,
};

describe("Recorte del clip", () => {
  it("ubica la selección donde cae dentro del video", () => {
    const { container } = render(
      <TrimTrack {...base} onChange={() => {}} onSeek={() => {}} />,
    );

    const seleccion = container.querySelector<HTMLElement>(".trim__selection");
    expect(seleccion?.style.left).toBe("20%");
    expect(seleccion?.style.width).toBe("40%");
  });

  it("la cabeza de reproducción va donde está el video", () => {
    const { container } = render(
      <TrimTrack {...base} onChange={() => {}} onSeek={() => {}} />,
    );

    expect(container.querySelector<HTMLElement>(".trim__playhead")?.style.left).toBe("35%");
  });

  it("muestra los tiempos y la duración resultante", () => {
    render(<TrimTrack {...base} onChange={() => {}} onSeek={() => {}} />);

    expect(screen.getByText("0:20")).toBeInTheDocument();
    expect(screen.getByText("1:00")).toBeInTheDocument();
    expect(screen.getByText("0:40 de clip")).toBeInTheDocument();
  });

  it("los extremos se pueden agarrar y dicen su tiempo", () => {
    render(<TrimTrack {...base} onChange={() => {}} onSeek={() => {}} />);

    expect(screen.getByLabelText("Comienzo del clip")).toHaveAttribute("title", "Comienzo: 0:20");
    expect(screen.getByLabelText("Final del clip")).toHaveAttribute("title", "Final: 1:00");
  });

  it("hacer clic en la barra mueve la reproducción", async () => {
    const onSeek = vi.fn();
    const { container } = render(
      <TrimTrack {...base} onChange={() => {}} onSeek={onSeek} />,
    );

    const track = container.querySelector<HTMLElement>(".trim__track")!;
    // jsdom no calcula tamaños: le damos uno para que la cuenta tenga sentido.
    track.getBoundingClientRect = () =>
      ({ left: 0, width: 200, top: 0, height: 34, right: 200, bottom: 34, x: 0, y: 0, toJSON: () => {} }) as DOMRect;

    await userEvent.pointer({ target: track, coords: { clientX: 100, clientY: 10 }, keys: "[MouseLeft]" });

    expect(onSeek).toHaveBeenCalled();
    expect(onSeek.mock.calls[0][0]).toBeCloseTo(50, 0);
  });

  it("no divide por cero cuando todavía no se sabe la duración", () => {
    const { container } = render(
      <TrimTrack duration={0} start={0} end={1} playhead={0} onChange={() => {}} onSeek={() => {}} />,
    );

    expect(container.querySelector(".trim__selection")).toBeInTheDocument();
  });
});
