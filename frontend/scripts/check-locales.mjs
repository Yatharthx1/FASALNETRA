// i18n-sync validation: every locale has exactly the source keys, and the same {placeholders} per key.
import { readFileSync } from "node:fs";

const SOURCE = "hi";
const LOCALES = ["en"];
const load = (l) => JSON.parse(readFileSync(new URL(`../src/locales/${l}.json`, import.meta.url), "utf8"));
const vars = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

const src = load(SOURCE);
let problems = 0;
for (const l of LOCALES) {
  const tgt = load(l);
  for (const k of Object.keys(src)) {
    if (!(k in tgt)) { console.error(`${l}: missing ${k}`); problems++; continue; }
    if (vars(src[k]) !== vars(tgt[k])) { console.error(`${l}: placeholder mismatch in ${k}`); problems++; }
    if (!tgt[k].trim()) { console.error(`${l}: empty ${k}`); problems++; }
  }
  for (const k of Object.keys(tgt)) if (!(k in src)) { console.error(`${l}: extra ${k}`); problems++; }
}
console.log(problems ? `${problems} locale problem(s)` : `locales ok: ${Object.keys(src).length} keys x ${LOCALES.length + 1} languages`);
process.exit(problems ? 1 : 0);
