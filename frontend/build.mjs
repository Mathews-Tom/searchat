import * as esbuild from "esbuild";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const watch = process.argv.includes("--watch");

const srcDir = resolve(__dirname, "../src/searchat/web/static/js/src");
const outDir = resolve(__dirname, "../src/searchat/web/static/js/dist");

const config = {
  entryPoints: [resolve(srcDir, "main.ts")],
  bundle: true,
  outfile: resolve(outDir, "main.js"),
  format: "esm",
  target: "es2022",
  sourcemap: true,
  minify: !watch,
  alias: {
    "@stores": resolve(srcDir, "stores"),
    "@modules": resolve(srcDir, "modules"),
    "@app-types": resolve(srcDir, "types"),
  },
  nodePaths: [resolve(__dirname, "node_modules")],
  logLevel: "info",
};

if (watch) {
  const ctx = await esbuild.context(config);
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(config);
}
