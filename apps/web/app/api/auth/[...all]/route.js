import { toNextJsHandler } from "better-auth/next-js";
import { createAuth } from "../../../../lib/auth";

export async function GET(request) {
  const { GET } = toNextJsHandler(await createAuth());
  return GET(request);
}

export async function POST(request) {
  const { POST } = toNextJsHandler(await createAuth());
  return POST(request);
}
