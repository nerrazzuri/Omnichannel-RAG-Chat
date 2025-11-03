try {
  // @ts-ignore - optional dependency; guard if not installed
  const Sentry = require('@sentry/nextjs');
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_RATE || '0.1'),
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT || 'staging',
    beforeSend(event: any) {
      // avoid sending PII
      if (event.user) {
        delete event.user.email;
        delete event.user.ip_address;
      }
      return event;
    }
  });
} catch (_) {
  // no-op when Sentry is not available
}


