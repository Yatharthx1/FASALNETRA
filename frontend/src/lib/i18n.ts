import en from "../locales/en.json";
import hi from "../locales/hi.json";

export type Lang = "hi" | "en";
export type Key = keyof typeof hi;
const TABLES: Record<Lang, Record<string, string>> = { hi, en };

/** t("walk.distance", { m: 38 }) -> "38 मीटर आगे". Missing keys fall back to Hindi, then to the key itself. */
export function t(key: Key, vars: Record<string, string | number> = {}, lang: Lang = "hi"): string {
  const raw = TABLES[lang][key] ?? TABLES.hi[key] ?? key;
  return raw.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
}

const CAUSE_KEYS: Record<string, Key> = {
  yellow_mosaic: "cause.yellow_mosaic", fungal: "cause.fungal", chewing_damage: "cause.chewing_damage",
  water_stress: "cause.water_stress", nutrient: "cause.nutrient",
};
export const causeName = (cause: string, lang: Lang = "hi") => (CAUSE_KEYS[cause] ? t(CAUSE_KEYS[cause], {}, lang) : cause);

/** Speak Hindi with the device's voice. Farmers never need to read: every step calls this. */
export function speak(text: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "hi-IN";
  u.rate = 0.9;
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("hi"));
  if (voice) u.voice = voice;
  window.speechSynthesis.speak(u);
}

export const fmt = (n: number, digits = 1) => n.toLocaleString("en-IN", { maximumFractionDigits: digits });
