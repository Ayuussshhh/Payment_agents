"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "../lib/auth-client";

const GROUPS = [
  {
    label: "Commerce",
    items: [
      { href: "/", label: "Checkout" },
      { href: "/policies", label: "Policies" },
      { href: "/approvals", label: "Approvals" },
      { href: "/payments", label: "Payments" },
    ],
  },
  {
    label: "Developer",
    items: [
      { href: "/agents", label: "Agents" },
      { href: "/skills", label: "Skills" },
      { href: "/models", label: "Models" },
      { href: "/usage", label: "Usage" },
      { href: "/keys", label: "API keys" },
    ],
  },
];

export default function Shell({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, isPending } = useSession();

  const signedIn = Boolean(session?.user);

  useEffect(() => {
    if (!isPending && !signedIn && pathname !== "/sign-in") {
      router.replace("/sign-in");
    }
  }, [isPending, signedIn, pathname, router]);

  if (pathname === "/sign-in") {
    return <>{children}</>;
  }

  if (isPending) {
    return <div className="boot">Loading…</div>;
  }

  if (!signedIn) {
    return <div className="boot">Redirecting to sign-in…</div>;
  }

  return (
    <div className="studio">
      <aside className="rail">
        <Link className="brand" href="/">
          <span className="mark">M</span>
          <span>
            <strong>Mandate</strong>
            <small>Studio</small>
          </span>
        </Link>
        <nav>
          {GROUPS.map((group) => (
            <div key={group.label} className="nav-group">
              <p className="nav-label">{group.label}</p>
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link key={item.href} href={item.href} className={active ? "nav active" : "nav"}>
                    {item.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="rail-foot">
          <p className="rail-user">{session.user.email}</p>
          <button
            className="link-button"
            onClick={async () => {
              await signOut();
              router.push("/sign-in");
              router.refresh();
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="stage">{children}</div>
    </div>
  );
}
