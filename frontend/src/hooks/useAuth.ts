import { useStore } from "../store";

export function useAuth() {
  const authToken = useStore((s) => s.authToken);
  const setAuthToken = useStore((s) => s.setAuthToken);

  return {
    token: authToken,
    isAuthenticated: !!authToken,
    login: (jwt: string) => setAuthToken(jwt),
    logout: () => setAuthToken(null),
  };
}
