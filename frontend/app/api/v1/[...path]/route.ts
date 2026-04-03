export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

function getBackendOrigin() {
  const explicit = process.env.BACKEND_ORIGIN?.trim();
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }

  const hostport = process.env.CANNABIA_API_HOSTPORT?.trim();
  if (hostport) {
    return `http://${hostport}`;
  }

  return "http://127.0.0.1:5000";
}

async function proxy(request: Request, context: RouteContext) {
  const { path = [] } = await context.params;
  const incomingUrl = new URL(request.url);
  const targetUrl = new URL(`${getBackendOrigin()}/api/v1/${path.join("/")}`);
  targetUrl.search = incomingUrl.search;

  const headers = new Headers();

  const accept = request.headers.get("accept");
  if (accept) {
    headers.set("accept", accept);
  }

  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.set("cookie", cookie);
  }

  const csrfToken = request.headers.get("x-csrf-token");
  if (csrfToken) {
    headers.set("x-csrf-token", csrfToken);
  }

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    const contentType = request.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      body = JSON.stringify(await request.json());
      headers.set("content-type", "application/json");
    } else {
      body = await request.text();
      if (contentType) {
        headers.set("content-type", contentType);
      }
    }

    headers.set("content-length", String(Buffer.byteLength(body, "utf8")));
  }

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  }).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : "Falha ao conectar ao backend.";
    return new Response(
      JSON.stringify({
        error: {
          code: "proxy_request_failed",
          message,
          details: {},
        },
      }),
      {
        status: 502,
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  });

  if (upstream instanceof Response && upstream.status === 502) {
    return upstream;
  }

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-length");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function OPTIONS(request: Request, context: RouteContext) {
  return proxy(request, context);
}
