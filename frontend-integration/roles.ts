export type Role = "USER" | "ENGINEER" | "OPERATOR" | "CHIEF_ENGINEER" | "ADMIN";

export type AuthUser = {
  roles?: string[];
};

export function hasRole(user: AuthUser | null | undefined, role: Role): boolean {
  if (!user?.roles || !Array.isArray(user.roles)) {
    return false;
  }
  return user.roles.includes(role);
}

export function isUser(user: AuthUser | null | undefined): boolean {
  return hasRole(user, "USER");
}

export function isEmployee(user: AuthUser | null | undefined): boolean {
  return (
    hasRole(user, "ENGINEER") ||
    hasRole(user, "OPERATOR") ||
    hasRole(user, "CHIEF_ENGINEER") ||
    hasRole(user, "ADMIN")
  );
}

export function getDefaultRouteByRole(user: AuthUser | null | undefined): string {
  if (hasRole(user, "ADMIN")) {
    return "/admin";
  }
  if (hasRole(user, "CHIEF_ENGINEER")) {
    return "/desktop/chief-engineer";
  }
  if (hasRole(user, "OPERATOR")) {
    return "/desktop/operator";
  }
  if (hasRole(user, "ENGINEER")) {
    return "/engineer/tasks";
  }
  return "/requests";
}

