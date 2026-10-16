// Live call events from the voice service (voice/app/browser_routes.py documents the protocol)
// folded into what the /call page shows. Pure, so it is easy to test.

export type Who = "agent" | "caller";
export type Lang = "ur" | "pa" | "ps" | "sd" | "skr" | "en" | "other";

export const LANGUAGE_NAMES: Record<Lang, string> = {
  ur: "Urdu",
  pa: "Punjabi",
  ps: "Pashto",
  sd: "Sindhi",
  skr: "Saraiki",
  en: "English",
  other: "Other",
};

export interface Turn {
  id: number;
  who: Who;
  text: string; // as transcribed (any script)
  final: boolean; // false while the agent is still speaking this turn
  order: number; // place on screen (a late caller line goes before the reply it prompted)
  at: number; // seconds into the call when it first appeared
  roman?: string; // Roman script, as people in Pakistan type it
  script?: string; // the language's own script (Urdu, Shahmukhi, Pashto, Sindhi)
  lang?: Lang;
}

export interface Lot {
  lot_id?: string;
  residue_label?: string;
  quantity_tonnes?: number;
  village?: string;
  district?: string;
  pickup_text?: string;
}

export interface Quote {
  lot_id?: string;
  price_per_tonne_rupees?: number;
  farmer_share_percent?: number;
  est_farmer_amount_rupees?: number;
  payment_timing?: string;
}

export interface CallView {
  turns: Turn[]; // in order of id
  lot?: Lot;
  quote?: Quote;
  escalated: boolean;
  confirmation?: { state?: string; farmer_amount_rupees?: number };
}

export const emptyView: CallView = { turns: [], escalated: false };

export type CallEvent =
  | { type: "transcript"; id: number; order?: number; who: Who; text: string; final: boolean }
  | { type: "roman"; id: number; roman: string; lang?: string; script?: string }
  | ({ type: "lot" } & Lot)
  | ({ type: "quote" } & Quote)
  | { type: "escalated" }
  | { type: "confirmation"; state?: string; farmer_amount_rupees?: number };

/** Apply one event; unknown or malformed events leave the view unchanged. */
export function applyEvent(view: CallView, event: CallEvent, secondsIn: number): CallView {
  switch (event.type) {
    case "transcript": {
      if (typeof event.id !== "number" || typeof event.text !== "string") return view;
      const existing = view.turns.find((t) => t.id === event.id);
      const order = typeof event.order === "number" ? event.order : event.id;
      const turn: Turn = existing
        ? { ...existing, text: event.text, final: event.final, order }
        : { id: event.id, who: event.who, text: event.text, final: event.final, order, at: secondsIn };
      const turns = view.turns.filter((t) => t.id !== event.id).concat(turn);
      return { ...view, turns: turns.sort((a, b) => a.order - b.order || a.id - b.id) };
    }
    case "roman":
      if (!event.roman) return view;
      return {
        ...view,
        turns: view.turns.map((t) =>
          t.id === event.id
            ? { ...t, roman: event.roman, script: event.script, lang: asLang(event.lang) }
            : t,
        ),
      };
    case "lot": {
      const { type: _type, ...lot } = event;
      // a different lot makes the old quote meaningless
      const quote = view.quote && view.quote.lot_id === lot.lot_id ? view.quote : undefined;
      return { ...view, lot, quote };
    }
    case "quote": {
      const { type: _type, ...quote } = event;
      if (quote.lot_id && view.lot?.lot_id && quote.lot_id !== view.lot.lot_id) return view; // stale
      return { ...view, quote };
    }
    case "escalated":
      return { ...view, escalated: true };
    case "confirmation":
      return { ...view, confirmation: { state: event.state, farmer_amount_rupees: event.farmer_amount_rupees } };
    default:
      return view;
  }
}

function asLang(lang?: string): Lang | undefined {
  if (lang === undefined) return undefined;
  return Object.prototype.hasOwnProperty.call(LANGUAGE_NAMES, lang) ? (lang as Lang) : "other";
}

// Arabic-script letters: the basic block (all Urdu, Punjabi, Pashto and Sindhi letters), the
// supplement (a few Saraiki letters such as \u0759) and presentation forms (not the U+FEFF BOM).
const ARABIC_SCRIPT = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFC]/;

/** BCP-47 tag for a line's own script, for screen readers and fonts. */
export function scriptLang(lang?: Lang): string | undefined {
  return { ur: "ur", pa: "pa-Arab", ps: "ps", sd: "sd", skr: "skr", en: undefined, other: undefined }[
    lang ?? "ur"
  ];
}

/** The two lines a turn shows: the romanised line when we have it, and the original script beneath.
 *  Until the Roman Urdu arrives the main line is the transcription itself; `rtl` says it is in
 *  Urdu script and should be laid out right to left. */
export function turnLines(turn: Turn): { main: string; rtl: boolean; script?: string } {
  const main = turn.roman ?? turn.text;
  const script = turn.script ?? (ARABIC_SCRIPT.test(turn.text) ? turn.text : undefined);
  return { main, rtl: !turn.roman && ARABIC_SCRIPT.test(main), script: script !== main ? script : undefined };
}

export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function rupees(amount?: number): string | undefined {
  return amount === undefined ? undefined : `Rs ${amount.toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;
}
