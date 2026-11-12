"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/agents", label: "Agents" },
  { href: "/policies", label: "Policies" },
  { href: "/approvals", label: "Approvals" },
  { href: "/skills", label: "Skills" },
  { href: "/models", label: "Models" },
  { href: "/runs", label: "Runs" },
];

export default function Shell({ children }) {
  const pathname = usePathname();

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
          {ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} className={active ? "nav active" : "nav"}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <p className="rail-note">The studio calls the engine. It does not approve a payment.</p>
      </aside>
      <div className="stage">{children}</div>
    </div>
  );
}
