import type { ReactNode } from "react";
import { useAuth } from "../hooks/useAuth";
import { LoginPage } from "./LoginPage";

interface AuthGateProps {
  children: ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <>{children}</>;
}
