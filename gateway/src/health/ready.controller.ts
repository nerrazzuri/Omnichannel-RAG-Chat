import { Controller, Get } from '@nestjs/common';

@Controller('ready')
export class ReadyController {
  @Get()
  getReady() {
    return {
      status: 'ok',
      service: 'gateway',
      timestamp: new Date().toISOString(),
    };
  }
}
