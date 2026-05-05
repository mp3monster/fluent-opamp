export function getCookie(name: string): string | null {
  const prefix = `${name}=`;
  const parts = document.cookie.split(';').map((item) => item.trim());
  for (const part of parts) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.substring(prefix.length));
    }
  }
  return null;
}

export function setCookie(name: string, value: string, days = 30): void {
  const expires = new Date();
  expires.setDate(expires.getDate() + days);
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

export function clearCookie(name: string): void {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}
