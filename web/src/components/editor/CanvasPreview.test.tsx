import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CanvasPreview } from "./CanvasPreview";

const base = {
  src: "/api/projects/p1/media",
  aspectRatio: "9:16",
  backgroundColor: "#204080",
};

describe("Vista previa del encuadre", () => {
  it("recorta el video cuando el encuadre sigue las caras", () => {
    const { container } = render(
      <CanvasPreview {...base} framing="faces" background="blur" />,
    );

    expect(container.querySelector(".preview__video")).toHaveClass("is-cropped");
    // No hay relleno: no sobra espacio que rellenar.
    expect(container.querySelector(".preview__blur")).toBeNull();
    expect(container.querySelector(".preview__flat")).toBeNull();
  });

  it("entra entero y usa una copia desenfocada como fondo", () => {
    const { container } = render(
      <CanvasPreview {...base} framing="fit" background="blur" />,
    );

    expect(container.querySelector(".preview__video")).toHaveClass("is-contained");
    const fondo = container.querySelector(".preview__blur");
    expect(fondo).toHaveAttribute("src", base.src);
    expect(fondo).toHaveAttribute("aria-hidden", "true");
  });

  it("usa el color elegido cuando el relleno es sólido", () => {
    const { container } = render(
      <CanvasPreview {...base} framing="fit" background="color" />,
    );

    const fondo = container.querySelector<HTMLElement>(".preview__flat");
    expect(fondo?.style.background).toContain("rgb(32, 64, 128)");
    expect(container.querySelector(".preview__blur")).toBeNull();
  });

  it("el degradado sale del color elegido", () => {
    const { container } = render(
      <CanvasPreview {...base} framing="fit" background="gradient" />,
    );

    const fondo = container.querySelector<HTMLElement>(".preview__flat");
    expect(fondo?.style.background).toContain("gradient");
  });

  it("el lienzo respeta la relación de aspecto pedida", () => {
    const { container, rerender } = render(
      <CanvasPreview {...base} framing="fit" background="blur" />,
    );
    // El navegador normaliza "0.5625" como "0.5625 / 1": comparamos el número.
    const proporcion = () => {
      const crudo = container.querySelector<HTMLElement>(".preview")?.style.aspectRatio ?? "";
      const [ancho, alto] = crudo.split("/").map((parte) => Number(parte.trim()));
      return alto ? ancho / alto : ancho;
    };

    expect(proporcion()).toBeCloseTo(9 / 16, 4);

    rerender(<CanvasPreview {...base} aspectRatio="1:1" framing="fit" background="blur" />);
    expect(proporcion()).toBeCloseTo(1, 4);
  });

  it("las guías de tercios se pueden apagar", () => {
    const { container } = render(
      <CanvasPreview {...base} framing="fit" background="blur" showGrid={false} />,
    );

    expect(container.querySelector(".preview__grid")).toBeNull();
  });
});
