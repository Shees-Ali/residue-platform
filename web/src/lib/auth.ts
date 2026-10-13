export type Role = "admin" | "transporter" | "factory" | "buyer";

export const routeRoles: Record<string, Role[]> = {
  "/admin": ["admin"],
  "/transporter": ["transporter", "admin"],
  "/factory": ["factory", "admin"],
  "/market": ["buyer", "factory", "admin"],
};

export function canAccess(path: string, role: Role | undefined): boolean {
  // TODO(A2): enforce role claims from the Firebase ID token (email or Google sign-in).
  const allowed = routeRoles[path];
  return !allowed || (role !== undefined && allowed.includes(role));
}
