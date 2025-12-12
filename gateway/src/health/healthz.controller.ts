import { Controller, Get } from '@nestjs/common';

@Controller()
export class HealthzController {
  @Get('healthz')
  healthz() {
    return 'OK';
  }
}
