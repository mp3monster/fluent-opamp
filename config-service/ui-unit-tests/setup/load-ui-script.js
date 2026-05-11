import fs from "node:fs";
import path from "node:path";

const HTML_DIR = path.resolve("src/config_service/html");

export function loadUiScript(fileName) {
  const scriptPath = path.join(HTML_DIR, fileName);
  const source = fs.readFileSync(scriptPath, "utf8");
  window.eval(source);
}
