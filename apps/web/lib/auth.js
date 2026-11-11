import { betterAuth } from "better-auth";
import { PostgresDialect } from "kysely";
import { Pool } from "pg";

function connectionString() {
  return (process.env.DATABASE_URL || "").replace(/^postgresql\+psycopg/, "postgresql");
}

export function createAuth() {
  const secret = process.env.BETTER_AUTH_SECRET;
  if (!secret) {
    throw new Error("BETTER_AUTH_SECRET is required before a sign-in.");
  }
  const pool = new Pool({ connectionString: connectionString() });
  return betterAuth({
    secret,
    baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3001",
    database: {
      dialect: new PostgresDialect({ pool }),
      type: "postgres",
      schemaName: "auth",
    },
    emailAndPassword: { enabled: true },
    advanced: {
      database: {
        generateId: "uuid",
      },
    },
  });
}
