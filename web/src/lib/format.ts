/** Formato de tiempos y fechas, en es-AR. */

const MESES = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

/** 74 → «1:14». 3725 → «1:02:05». Para timecodes de la transcripción. */
export function timecode(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const s = total % 60;
  const m = Math.floor(total / 60) % 60;
  const h = Math.floor(total / 3600);
  const pad = (value: number) => String(value).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** 74 → «1 min 14 s». Para duraciones que se leen, no que se buscan. */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes < 60) return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

/** ISO → «17 ago, 13:30». */
export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const time = `${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`;
  return `${date.getDate()} ${MESES[date.getMonth()]}, ${time}`;
}

/** Una URL larga o un path largo, recortados por el medio. */
export function shortSource(source: string, max = 52): string {
  if (source.length <= max) return source;
  const head = Math.ceil((max - 1) / 2);
  return `${source.slice(0, head)}…${source.slice(-(max - head - 1))}`;
}
