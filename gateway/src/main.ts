import './utils/secretLoader';
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import rateLimit from 'express-rate-limit';
import { planRateLimit } from './rate/planLimiter';
import { planGuard } from './middleware/planGuard';
import { planHeader } from './middleware/planHeader';
import { startWebhookWorker } from './queue/retryQueue';
import { hostTenant } from './middleware/hostTenant';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Enable global validation pipes
  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    transform: true,
  }));

  // Enable CORS
  app.enableCors({
    origin: true,
    methods: 'GET,HEAD,PUT,PATCH,POST,DELETE',
    credentials: true,
  });

  // Trust reverse proxy for rate limit and IP extraction
  app.getHttpAdapter().getInstance().set('trust proxy', 1);

  // Basic rate limiting (per-IP); for distributed setups, back with Redis store
  const limiter = rateLimit({ windowMs: 60_000, max: 0 }); // disabled; prefer plan-based limiter below
  app.use(planRateLimit());
  app.use(planGuard());
  app.use(planHeader());
  app.use(hostTenant());

  // Start Redis-backed webhook worker
  startWebhookWorker();

  // Global prefix for API routes
  app.setGlobalPrefix('api');

  const port = process.env.PORT || 3001;
  await app.listen(port);

  console.log(`Gateway service is running on port ${port}`);
}

bootstrap();
