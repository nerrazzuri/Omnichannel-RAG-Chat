import { Controller, Post, Body, Headers, BadRequestException } from '@nestjs/common';
import { WebhookService } from './webhook.service';

@Controller('webhooks')
export class WebhookController {
  constructor(private readonly webhookService: WebhookService) {}

  @Post('whatsapp')
  async handleWhatsApp(@Body() body: any, @Headers() headers: any) {
    try {
      return await this.webhookService.processWhatsAppWebhook(body, headers);
    } catch (error) {
      throw new BadRequestException('Invalid WhatsApp webhook payload');
    }
  }

  @Post('teams')
  async handleTeams(@Body() body: any) {
    try {
      return await this.webhookService.processTeamsWebhook(body);
    } catch (error) {
      throw new BadRequestException('Invalid Teams webhook payload');
    }
  }

  @Post('telegram')
  async handleTelegram(@Body() body: any) {
    try {
      return await this.webhookService.processTelegramWebhook(body);
    } catch (error) {
      throw new BadRequestException('Invalid Telegram webhook payload');
    }
  }

  @Post('wechat')
  async handleWeChat(@Body() body: any, @Headers() headers: any) {
    try {
      return await this.webhookService.processWeChatWebhook(body, headers);
    } catch (error) {
      throw new BadRequestException('Invalid WeChat webhook payload');
    }
  }

  @Post('line')
  async handleLine(@Body() body: any, @Headers() headers: any) {
    try {
      return await this.webhookService.processLineWebhook(body, headers);
    } catch (error) {
      throw new BadRequestException('Invalid LINE webhook payload');
    }
  }
}
