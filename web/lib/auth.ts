import Cookies from "js-cookie";

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

const cookieOptions = {
  expires: 7,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export function getAccessToken(): string | undefined {
  return Cookies.get(ACCESS_KEY);
}

export function getRefreshToken(): string | undefined {
  return Cookies.get(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  Cookies.set(ACCESS_KEY, access, cookieOptions);
  Cookies.set(REFRESH_KEY, refresh, cookieOptions);
}

export function clearTokens(): void {
  Cookies.remove(ACCESS_KEY, { path: "/" });
  Cookies.remove(REFRESH_KEY, { path: "/" });
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}

export function isAuthPath(pathname?: string): boolean {
  const path =
    pathname ?? (typeof window !== "undefined" ? window.location.pathname : "");
  return path === "/login" || path === "/register";
}
