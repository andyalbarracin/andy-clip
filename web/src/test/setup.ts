import "@testing-library/jest-dom/vitest";

// Atlassian Design System consulta el esquema de color del sistema al cargarse.
// jsdom no implementa matchMedia, así que le damos una respuesta fija.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: query.includes("dark"),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
