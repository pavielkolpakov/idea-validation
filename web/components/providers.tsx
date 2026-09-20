"use client";

import {
  ClerkProvider,
  SignInButton,
  UserButton,
  useAuth,
  useUser,
} from "@clerk/nextjs";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  claimReports,
  errorMessage,
  listReports,
  type ReportSummary,
} from "@/lib/api";

const noToken = async () => null;
const IdentityContext = createContext({
  ready: true,
  signedIn: false,
  userId: "",
  name: "Personal workspace",
  getToken: noToken as () => Promise<string | null>,
  configured: false,
});
export const useIdentity = () => useContext(IdentityContext);
const HistoryContext = createContext({
  reports: [] as ReportSummary[],
  loading: true,
  error: "",
  claimError: "",
  refresh: () => {},
  retryClaim: () => {},
});
export const useHistory = () => useContext(HistoryContext);

function ClerkIdentity({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  return (
    <IdentityContext.Provider
      value={{
        ready: isLoaded,
        signedIn: !!isSignedIn,
        userId: user?.id ?? "",
        name: user?.firstName
          ? `${user.firstName}’s workspace`
          : "Personal workspace",
        getToken,
        configured: true,
      }}
    >
      {children}
    </IdentityContext.Provider>
  );
}
function HistoryProvider({ children }: { children: ReactNode }) {
  const { ready, signedIn, getToken, userId } = useIdentity();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [claimError, setClaimError] = useState("");
  const [revision, setRevision] = useState(0);
  const [claimRevision, setClaimRevision] = useState(0);
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError("");
      setReports([]);
      try {
        const token = await getToken();
        if (signedIn && !token) throw new Error("Session unavailable");
        const data = await listReports({ token, signal: controller.signal });
        if (!controller.signal.aborted) setReports(data);
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [ready, signedIn, getToken, userId, revision]);
  useEffect(() => {
    if (!ready || !signedIn) return;
    const controller = new AbortController();
    async function claim() {
      setClaimError("");
      try {
        const token = await getToken();
        if (!token) throw new Error("Session unavailable");
        await claimReports({ token, signal: controller.signal });
        if (!controller.signal.aborted) refresh();
      } catch (e) {
        if (!controller.signal.aborted) setClaimError(errorMessage(e));
      }
    }
    void claim();
    return () => controller.abort();
  }, [ready, signedIn, getToken, userId, refresh, claimRevision]);
  return (
    <HistoryContext.Provider
      value={{
        reports,
        loading,
        error,
        claimError: signedIn ? claimError : "",
        refresh,
        retryClaim: () => setClaimRevision((n) => n + 1),
      }}
    >
      {children}
    </HistoryContext.Provider>
  );
}
export function Providers({ children }: { children: ReactNode }) {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!key) return <HistoryProvider>{children}</HistoryProvider>;
  return (
    <ClerkProvider
      publishableKey={key}
      appearance={{
        variables: { colorPrimary: "#284d33", borderRadius: "1rem" },
      }}
    >
      <ClerkIdentity>
        <HistoryProvider>{children}</HistoryProvider>
      </ClerkIdentity>
    </ClerkProvider>
  );
}
export function AccountAction({
  className = "button secondary",
  label = "Sign in",
}: {
  className?: string;
  label?: string;
}) {
  const { configured, ready, signedIn } = useIdentity();
  const [notice, setNotice] = useState(false);
  if (!configured)
    return (
      <span className="account-action">
        <button
          type="button"
          className={className}
          onClick={() => setNotice(!notice)}
        >
          {label}
        </button>
        {notice && (
          <span className="account-notice" role="status">
            Account access isn’t available yet. You can still try one report as
            a guest.
          </span>
        )}
      </span>
    );
  if (!ready) return <span className="muted">Loading account…</span>;
  return signedIn ? (
    <UserButton />
  ) : (
    <SignInButton mode="modal">
      <button type="button" className={className}>
        {label}
      </button>
    </SignInButton>
  );
}
