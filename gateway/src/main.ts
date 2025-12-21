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

  // 🔴 FAST LIVENESS — BYPASS ALL BUSINESS MIDDLEWARE
  app.use((req, res, next) => {
    if (req.url === '/healthz') {
      res.status(200).send('OK');
      return;
    }
    next();
  });

  // Enable global validation pipes
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    })
  );

  // Enable CORS
  app.enableCors({
    origin: true,
    methods: 'GET,HEAD,PUT,PATCH,POST,DELETE',
    credentials: true,
  });

  // Trust reverse proxy for correct client IP
  app.getHttpAdapter().getInstance().set('trust proxy', 1);

  // Plan-aware middleware and headers
  app.use(planRateLimit());
  app.use(planGuard());
  app.use(planHeader());
  app.use(hostTenant());

  // Start background worker
  startWebhookWorker();

  // Global API prefix
  app.setGlobalPrefix('api');

  const port = process.env.PORT || 3001;
  await app.listen(port);
  // eslint-disable-next-line no-console
  console.log(`Gateway service is running on port ${port}`);
}

bootstrap();
