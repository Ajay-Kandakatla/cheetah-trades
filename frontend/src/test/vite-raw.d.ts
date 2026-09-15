/* Vite's `?raw` import — the file's text as a string, read at transform time.
 * Declared here because the project does not reference `vite/client` types.
 * First use: src/lib/bounceRoom.test.ts reading the backend's ordering
 * fixture (2026-09-14), so one JSON file pins both sort implementations. */
declare module '*?raw' {
  const raw: string;
  export default raw;
}
