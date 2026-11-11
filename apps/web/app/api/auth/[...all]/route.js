import { toNextJsHandler } from "better-auth/next-js";
import { createAuth } from "../../../../lib/auth";

const handler = () => toNextJsHandler(createAuth());

export function GET(request) {
  return handler().GET(request);
}

export function POST(request) {
  return handler().POST(request);
}
