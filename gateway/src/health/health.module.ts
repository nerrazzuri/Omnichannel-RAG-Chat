import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
import { HealthzController } from './healthz.controller';
import { ReadyController } from './ready.controller';

@Module({
  controllers: [HealthController, ReadyController, HealthzController],
})
export class HealthModule {}
