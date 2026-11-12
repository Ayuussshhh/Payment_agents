import { betterAuth } from "better-auth";
import { PostgresDialect } from "kysely";
import { Pool } from "pg";
import dns from "node:dns";

function connectionString() {
  return (process.env.DATABASE_URL || "").replace(/^postgresql\+psycopg/, "postgresql");
}

// Some ISP resolvers refuse to resolve Neon hostnames. The Python engine works
// around this with a Cloudflare DNS fallback; Node's pg has none, so Better Auth
// fails with ENOTFOUND. This mirrors that: if the system can't resolve the host,
// resolve it via 1.1.1.1 and connect by IP while keeping the hostname for TLS SNI
// (which Neon needs for routing and certificate validation).
async function resolvedPoolConfig() {
  const url = new URL(connectionString());
  const hostname = url.hostname;
  const config = {
    host: hostname,
    port: url.port ? Number(url.port) : 5432,
    user: decodeURIComponent(url.username),
    password: decodeURIComponent(url.password),
    database: url.pathname.replace(/^\//, ""),
    ssl: { rejectUnauthorized: true, servername: hostname },
  };
  try {
    await dns.promises.lookup(hostname);
  } catch {
    try {
      const resolver = new dns.promises.Resolver();
      resolver.setServers(["1.1.1.1", "8.8.8.8"]);
      const addresses = await resolver.resolve4(hostname);
      if (addresses && addresses.length) {
        config.host = addresses[0];
      }
    } catch {
      // Leave the hostname in place; the connection will surface the error.
    }
  }
  return config;
}

let cached;

export async function createAuth() {
  if (cached) return cached;
  const secret = process.env.BETTER_AUTH_SECRET;
  if (!secret) {
    throw new Error("BETTER_AUTH_SECRET is required before a sign-in.");
  }
  const pool = new Pool(await resolvedPoolConfig());
  cached = betterAuth({
    secret,
    baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3001",
    database: {
      dialect: new PostgresDialect({ pool }),
      type: "postgres",
      schemaName: "auth",
    },
    emailAndPassword: { enabled: true },
    session: {
      // Cache the session in a signed cookie so getSession does not hit the
      // database on every request. This is the big latency win behind the proxy.
      cookieCache: { enabled: true, maxAge: 300 },
    },
    advanced: {
      database: {
        generateId: "uuid",
      },
    },
  });
  return cached;
}
