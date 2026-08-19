import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Dos archivos no pueden definir la misma clase.
 *
 * Este test existe por un error concreto: `.canvas` nombraba a la vez el área
 * principal de la aplicación y el lienzo de previsualización del editor. Las
 * reglas del lienzo —borde, fondo negro, `max-height: 58vh`— se aplicaron a
 * toda la app, que pasó a verse como una pantallita en el medio de la nada.
 *
 * El CSS es global: el compilador no avisa. Este test sí.
 */
const RAIZ = join(__dirname, "..");

// Clases que a propósito se comparten entre pantallas.
const COMPARTIDAS = new Set([
  "mono",
  "muted",
  "small",
  "sr-only",
  "stack",
  "link-quiet",
  "source-tag",
]);

function archivosCss(directorio: string): string[] {
  return readdirSync(directorio).flatMap((entrada) => {
    const ruta = join(directorio, entrada);
    if (statSync(ruta).isDirectory()) return archivosCss(ruta);
    return ruta.endsWith(".css") ? [ruta] : [];
  });
}

/**
 * Los nombres de clase que un archivo **define**.
 *
 * La dueña de un bloque es la primera clase de cada selector: en
 * `.provider__key .input` el archivo define `provider__key` y solo referencia
 * `.input`, que vive en otro lado. Sin esta distinción, cualquier selector
 * descendente daría un choque falso.
 */
function clasesDefinidas(css: string): Set<string> {
  const clases = new Set<string>();
  // Sin comentarios: un `/* … */` delante del selector escondía la clase y el
  // detector dejaba pasar justo lo que tiene que encontrar.
  const limpio = css.replace(/\/\*[\s\S]*?\*\//g, "");

  for (const [, bloque] of limpio.matchAll(/([^{}]+)\{/g)) {
    if (bloque.includes("@media") || bloque.includes("@import")) continue;
    for (const selector of bloque.split(",")) {
      const primera = selector.trim().match(/^\.([a-zA-Z][\w-]*)/);
      if (primera) clases.add(primera[1]);
    }
  }
  return clases;
}

describe("hojas de estilo", () => {
  it("ninguna clase se define en dos archivos distintos", () => {
    const duenos = new Map<string, string[]>();

    for (const ruta of archivosCss(RAIZ)) {
      const relativa = ruta.replace(RAIZ + "/", "");
      for (const clase of clasesDefinidas(readFileSync(ruta, "utf8"))) {
        if (COMPARTIDAS.has(clase)) continue;
        duenos.set(clase, [...(duenos.get(clase) ?? []), relativa]);
      }
    }

    const chocadas = [...duenos.entries()]
      .filter(([, archivos]) => new Set(archivos).size > 1)
      .map(([clase, archivos]) => `.${clase} → ${[...new Set(archivos)].join(", ")}`);

    expect(chocadas).toEqual([]);
  });

  it("el área principal y el lienzo del editor tienen nombres distintos", () => {
    const shell = readFileSync(join(RAIZ, "components/AppShell.css"), "utf8");
    const preview = readFileSync(join(RAIZ, "components/editor/CanvasPreview.css"), "utf8");

    expect(clasesDefinidas(shell).has("workspace")).toBe(true);
    expect(clasesDefinidas(preview).has("preview")).toBe(true);
    expect(clasesDefinidas(shell).has("preview")).toBe(false);
  });
});
