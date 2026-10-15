import { cloneElement, useId, type ReactElement } from "react";

interface FieldProps {
  label: string;
  /** The message to show under the input; marks it invalid. */
  error?: string;
  hint?: string;
  /** One input, select or textarea. It gets id, aria-invalid and aria-describedby. */
  children: ReactElement<{ id?: string; "aria-invalid"?: boolean; "aria-describedby"?: string }>;
}

/** Label, input and an explicit error message, wired for screen readers. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const input = cloneElement(children, {
    id,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error || hint ? noteId : undefined,
  });
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      {input}
      {(error || hint) && (
        <p id={noteId} className={error ? "field-error" : "field-hint"}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
