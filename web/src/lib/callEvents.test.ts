import { applyEvent, clock, emptyView, rupees, scriptLang, turnLines, type CallEvent } from "./callEvents";

const run = (events: CallEvent[]) => events.reduce((v, e, i) => applyEvent(v, e, i * 5), emptyView);

test("agent turns grow while speaking, then finalise in place", () => {
  const view = run([
    { type: "transcript", id: 1, who: "agent", text: "Assalam", final: false },
    { type: "transcript", id: 1, who: "agent", text: "Assalam o alaikum", final: false },
    { type: "transcript", id: 1, who: "agent", text: "Assalam o alaikum ji", final: true },
  ]);
  expect(view.turns).toHaveLength(1);
  expect(view.turns[0]).toMatchObject({ text: "Assalam o alaikum ji", final: true, at: 0 });
});

test("turns stay in id order and Roman Urdu attaches to its turn", () => {
  const view = run([
    { type: "transcript", id: 2, who: "agent", text: "جی بالکل", final: true },
    { type: "transcript", id: 1, who: "caller", text: "گندم کا بھوسا ہے", final: true },
    { type: "roman", id: 1, roman: "Gandum ka bhoosa hai", lang: "ur", script: "گندم کا بھوسا ہے" },
  ]);
  expect(view.turns.map((t) => t.id)).toEqual([1, 2]);
  expect(turnLines(view.turns[0])).toEqual({
    main: "Gandum ka bhoosa hai",
    rtl: false,
    script: "گندم کا بھوسا ہے",
  });
  // not romanised yet: shows the transcription right to left, and only once
  expect(turnLines(view.turns[1])).toEqual({ main: "جی بالکل", rtl: true, script: undefined });
});

test("each line keeps its language; unknown tags become other", () => {
  const view = run([
    { type: "transcript", id: 1, who: "caller", text: "د غنمو بوس", final: true },
    { type: "roman", id: 1, roman: "Da ghanamo bus", lang: "ps", script: "د غنمو بوس" },
    { type: "transcript", id: 2, who: "caller", text: "x", final: true },
    { type: "roman", id: 2, roman: "x", lang: "klingon" },
  ]);
  expect(view.turns.map((t) => t.lang)).toEqual(["ps", "other"]);
  expect(turnLines(view.turns[0]).script).toBe("د غنمو بوس");
});

test("Saraiki letters outside the basic block count as script; a stray BOM does not", () => {
  const view = run([
    { type: "transcript", id: 1, who: "caller", text: "\u0759", final: true },
    { type: "transcript", id: 2, who: "caller", text: "\uFE8D", final: true },
    { type: "transcript", id: 3, who: "caller", text: "\uFEFFHello", final: true },
  ]);
  expect(view.turns.map((t) => turnLines(t).rtl)).toEqual([true, true, false]);
});

test("prototype keys are not languages", () => {
  const view = run([
    { type: "transcript", id: 1, who: "caller", text: "x", final: true },
    { type: "roman", id: 1, roman: "x", lang: "__proto__" },
  ]);
  expect(view.turns[0].lang).toBe("other");
  expect(scriptLang("pa")).toBe("pa-Arab");
  expect(scriptLang("en")).toBeUndefined();
});

test("a Latin-script line without Roman Urdu has no script line", () => {
  const view = run([{ type: "transcript", id: 1, who: "caller", text: "Hello ji", final: true }]);
  expect(turnLines(view.turns[0])).toEqual({ main: "Hello ji", rtl: false, script: undefined });
});

test("a caller line sent late is placed before the reply it prompted", () => {
  const view = run([
    { type: "transcript", id: 1, order: 1, who: "agent", text: "Ji,", final: false },
    { type: "transcript", id: 2, order: 0.5, who: "caller", text: "Gandum", final: true },
  ]);
  expect(view.turns.map((t) => t.who)).toEqual(["caller", "agent"]);
});

test("a new lot drops the old quote, and a quote for another lot is ignored", () => {
  const view = run([
    { type: "lot", lot_id: "A", quantity_tonnes: 2 },
    { type: "quote", lot_id: "A", price_per_tonne_rupees: 7000 },
    { type: "lot", lot_id: "B", quantity_tonnes: 5 },
  ]);
  expect(view.quote).toBeUndefined();
  const late = applyEvent(view, { type: "quote", lot_id: "A", price_per_tonne_rupees: 7000 }, 0);
  expect(late.quote).toBeUndefined();
  const right = applyEvent(view, { type: "quote", lot_id: "B", price_per_tonne_rupees: 6500 }, 0);
  expect(right.quote?.price_per_tonne_rupees).toBe(6500);
});

test("saved lot, quote and escalation are captured; junk is ignored", () => {
  const view = run([
    { type: "lot", lot_id: "7f3a9c00-0000", residue_label: "Wheat straw", quantity_tonnes: 2 },
    { type: "quote", price_per_tonne_rupees: 7000, farmer_share_percent: 70 },
    { type: "escalated" },
    { type: "nonsense" } as unknown as CallEvent,
    { type: "transcript", id: "x", text: 5 } as unknown as CallEvent,
  ]);
  expect(view.lot).toEqual({ lot_id: "7f3a9c00-0000", residue_label: "Wheat straw", quantity_tonnes: 2 });
  expect(view.quote).toEqual({ price_per_tonne_rupees: 7000, farmer_share_percent: 70 });
  expect(view.escalated).toBe(true);
  expect(view.turns).toEqual([]);
});

test("formatting helpers", () => {
  expect(clock(154.7)).toBe("02:34");
  expect(rupees(7000)).toBe("Rs 7,000");
  expect(rupees(undefined)).toBeUndefined();
});
