try {
  // @ts-ignore - optional dependency; guard if not installed
  const Sentry = require("@sentry/nextjs");
  Sentry.init({
    dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN || "",
    tracesSampleRate: Number(process.env.SENTRY_TRACES_RATE || "0.1"),
    environment:
      process.env.ENVIRONMENT ||
      process.env.NEXT_PUBLIC_ENVIRONMENT ||
      "staging",
    sendDefaultPii: false,
  });
} catch (_) {
  // no-op when Sentry is not available
}
