import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { WebhookModule } from './webhook/webhook.module';
import { HealthModule } from './health/health.module';
import { MetricsController } from './metrics/metrics.controller';
import { AuthController } from './auth/auth.controller';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),
    WebhookModule,
    HealthModule,
  ],
  controllers: [MetricsController, AuthController],
  providers: [],
})
export class AppModule {}
