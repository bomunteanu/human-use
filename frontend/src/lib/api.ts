const BASE_URL = "http://localhost:8000";

function getToken(): string | null {
  return localStorage.getItem("jwt");
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers as Record<string, string> | undefined ?? {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("jwt");
    window.location.reload();
  }
  return res;
}
