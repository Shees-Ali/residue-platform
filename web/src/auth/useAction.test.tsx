import { act, fireEvent, screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/renderApp";
import { useAction } from "./useAction";

function Probe({ action }: { action: () => Promise<void> }) {
  const { busy, run, cancel } = useAction();
  return (
    <>
      <button onClick={() => void run(action)}>{busy ? "working" : "idle"}</button>
      <button onClick={cancel}>cancel</button>
    </>
  );
}

const deferred = () => {
  let resolve!: () => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<void>((res, rej) => ((resolve = res), (reject = rej)));
  return { promise, resolve, reject };
};

test("busy lasts exactly as long as the action and clears when it settles", async () => {
  const d = deferred();
  renderWithProviders(<Probe action={() => d.promise} />);
  fireEvent.click(screen.getByText("idle"));
  expect(screen.getByText("working")).toBeInTheDocument();
  await act(async () => {}); // time passing alone never clears it
  expect(screen.getByText("working")).toBeInTheDocument();
  await act(async () => d.resolve());
  expect(screen.getByText("idle")).toBeInTheDocument();
});

test("busy clears after an error, and the error is toasted", async () => {
  renderWithProviders(<Probe action={() => Promise.reject({ code: "auth/invalid-credential" })} />);
  fireEvent.click(screen.getByText("idle"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
  expect(screen.getByText("idle")).toBeInTheDocument();
});

test("a window that never reports closing keeps spinning until the person cancels", async () => {
  vi.useFakeTimers();
  try {
    renderWithProviders(<Probe action={() => new Promise<void>(() => {})} />);
    fireEvent.click(screen.getByText("idle"));
    act(() => {
      window.dispatchEvent(new Event("focus")); // focus coming back is not a response
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByText("working")).toBeInTheDocument();
    fireEvent.click(screen.getByText("cancel"));
    expect(screen.getByText("idle")).toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

test("a cancelled run that finishes late cannot clear a newer run", async () => {
  const first = deferred();
  const second = deferred();
  const actions = [first, second];
  renderWithProviders(<Probe action={() => actions.shift()!.promise} />);
  fireEvent.click(screen.getByText("idle"));
  fireEvent.click(screen.getByText("cancel"));
  fireEvent.click(screen.getByText("idle")); // a second attempt is now in flight
  await act(async () => first.resolve()); // the cancelled one finishes
  expect(screen.getByText("working")).toBeInTheDocument();
  await act(async () => second.resolve());
  expect(screen.getByText("idle")).toBeInTheDocument();
});

test("a replaced popup request is not shown as an error", async () => {
  renderWithProviders(<Probe action={() => Promise.reject({ code: "auth/cancelled-popup-request" })} />);
  fireEvent.click(screen.getByText("idle"));
  await screen.findByText("idle");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
