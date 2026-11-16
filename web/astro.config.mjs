import { defineConfig } from 'astro/config';

// Static output, no UI framework: the page ships one small vanilla script.
export default defineConfig({
  build: { inlineStylesheets: 'always' },
  server: { port: 4321 },
});
