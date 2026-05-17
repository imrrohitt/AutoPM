import type { GlobalRole, ProjectRole } from "./types";

export function isGlobalAdmin(role: GlobalRole): boolean {
  return role === "owner" || role === "admin";
}

export function canCreateProject(globalRole: GlobalRole): boolean {
  return isGlobalAdmin(globalRole);
}

export function canDeleteProject(globalRole: GlobalRole): boolean {
  return isGlobalAdmin(globalRole);
}

export function canManageProjectMembers(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  if (isGlobalAdmin(globalRole)) return true;
  return projectRole === "manager";
}

export function canConfigureIntegrations(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  return canManageProjectMembers(globalRole, projectRole);
}

export function canCreateStory(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  if (isGlobalAdmin(globalRole)) return true;
  return projectRole === "manager";
}

export function canCreateTicket(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  if (isGlobalAdmin(globalRole)) return true;
  return projectRole === "manager" || projectRole === "developer";
}

export function canEnableAgent(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  return canCreateTicket(globalRole, projectRole);
}

export function canComment(
  globalRole: GlobalRole,
  projectRole?: ProjectRole | null
): boolean {
  return canCreateTicket(globalRole, projectRole);
}

export function canInviteUsers(globalRole: GlobalRole): boolean {
  return isGlobalAdmin(globalRole);
}

export function canChangeGlobalRole(globalRole: GlobalRole): boolean {
  return globalRole === "owner";
}
