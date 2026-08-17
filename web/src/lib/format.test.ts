import { describe, expect, it } from "vitest";

import { duration, shortSource, timecode } from "./format";

describe("timecode", () => {
  it("omite la hora cuando el video es corto", () => {
    expect(timecode(74)).toBe("1:14");
  });

  it("muestra la hora cuando hace falta", () => {
    expect(timecode(3725)).toBe("1:02:05");
  });

  it("no rompe con negativos", () => {
    expect(timecode(-5)).toBe("0:00");
  });
});

describe("duration", () => {
  it("usa segundos abajo del minuto", () => {
    expect(duration(45)).toBe("45 s");
  });

  it("combina minutos y segundos", () => {
    expect(duration(74)).toBe("1 min 14 s");
  });

  it("redondea a minutos exactos", () => {
    expect(duration(120)).toBe("2 min");
  });

  it("muestra un guión cuando no hay dato", () => {
    expect(duration(null)).toBe("—");
  });
});

describe("shortSource", () => {
  it("deja las cortas como están", () => {
    expect(shortSource("https://youtu.be/abc")).toBe("https://youtu.be/abc");
  });

  it("recorta por el medio para conservar el final", () => {
    const long = `https://www.youtube.com/watch?v=${"x".repeat(80)}&t=42s`;
    const short = shortSource(long, 30);

    expect(short).toHaveLength(30);
    expect(short).toContain("…");
    expect(short.endsWith("t=42s")).toBe(true);
  });
});
