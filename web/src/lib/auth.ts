export type Role = "admin" | "transporter" | "factory" | "buyer" | "farmer";
export type AccountStatus = "active" | "pending" | "suspended";

/** Roles a person may pick at signup. Admin is never self-selected (the API refuses it). */
export const SIGNUP_ROLES: { role: Exclude<Role, "admin">; label: string; blurb: string }[] = [
  { role: "farmer", label: "Farmer", blurb: "Sell crop residue and track payments." },
  { role: "transporter", label: "Transporter", blurb: "Carry loads. An admin approves you first." },
  { role: "factory", label: "Factory", blurb: "Buy residue, sell products. An admin approves you first." },
  { role: "buyer", label: "Buyer", blurb: "Shop the marketplace." },
];

// Who may open each page. The API enforces the same rules; this only decides what the UI shows.
export const routeRoles: Record<string, Role[]> = {
  "/farmer": ["farmer", "admin"],
  "/transporter": ["transporter", "admin"],
  "/factory": ["factory", "admin"],
  "/market": ["buyer", "factory", "admin"],
  "/admin": ["admin"],
  "/call": ["admin"],
};

export function canAccess(path: string, role: Role | undefined): boolean {
  const allowed = routeRoles[path];
  return !allowed || (role !== undefined && allowed.includes(role));
}

const HOME: Record<Role, string> = {
  admin: "/admin",
  transporter: "/transporter",
  factory: "/factory",
  buyer: "/market",
  farmer: "/farmer",
};

/** Where a signed-in person lands. */
export function homeFor(role: Role): string {
  return HOME[role];
}
