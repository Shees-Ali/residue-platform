import { act, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider, useToast } from "./toast";

function Trigger({ message }: { message: string }) {
  const toast = useToast();
  return <button onClick={() => toast.error(message)}>boom</button>;
}

afterEach(() => vi.useRealTimers());

test("an error toast is announced, can be dismissed, and goes away by itself", () => {
  vi.useFakeTimers();
  render(
    <ToastProvider>
      <Trigger message="Invalid token" />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByText("boom"));
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid token");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();

  fireEvent.click(screen.getByText("boom"));
  act(() => void vi.advanceTimersByTime(8000));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("the same message twice shows once", () => {
  render(
    <ToastProvider>
      <Trigger message="Same" />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByText("boom"));
  fireEvent.click(screen.getByText("boom"));
  expect(screen.getAllByRole("alert")).toHaveLength(1);
});

test("without a provider a toast call is harmless", () => {
  render(<Trigger message="x" />);
  fireEvent.click(screen.getByText("boom"));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
