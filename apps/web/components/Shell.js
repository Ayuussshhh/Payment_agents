"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "../lib/auth-client";

const GROUPS = [
  {
    label: "Build",
    items: [
      { href: "/", label: "Overview" },
      { href: "/agents", label: "Agents" },
      { href: "/skills", label: "Skills" },
      { href: "/models", label: "Models" },
      { href: "/runs", label: "Runs" },
    ],
  },
  {
    label: "Spend",
    items: [
      { href: "/policies", label: "Policies" },
      { href: "/approvals", label: "Approvals" },
      { href: "/payments", label: "Payments" },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/usage", label: "Usage" },
      { href: "/keys", label: "API keys" },
    ],
  },
];

export default function Shell({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();

  if (pathname === "/sign-in") {
    return <>{children}</>;
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
          {session?.user ? (
            <>
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
            </>
          ) : (
            <Link className="link-button" href="/sign-in">
              Sign in
            </Link>
          )}
        </div>
      </aside>
      <div className="stage">{children}</div>
    </div>
  );
}
