import { Controller, Post, Body, Headers, BadRequestException, UseGuards, Req } from '@nestjs/common';
import { WebhookService } from './webhook.service';
import { AuthGuard } from '../auth/auth.guard';

@Controller('webhooks')
export class WebhookController {
  constructor(private readonly webhookService: WebhookService) {}

  @Post('whatsapp')
  @UseGuards(new AuthGuard('webhook:write'))
  async handleWhatsApp(@Body() body: any, @Headers() headers: any, @Req() req: any) {
    try {
      return await this.webhookService.processWhatsAppWebhook(body, headers, req.user);
    } catch (error) {
      throw new BadRequestException('Invalid WhatsApp webhook payload');
    }
  }

  @Post('teams')
  @UseGuards(new AuthGuard('webhook:write'))
  async handleTeams(@Body() body: any, @Req() req: any) {
    try {
      return await this.webhookService.processTeamsWebhook(body, req.user);
    } catch (error) {
      throw new BadRequestException('Invalid Teams webhook payload');
    }
  }

  @Post('telegram')
  @UseGuards(new AuthGuard('webhook:write'))
  async handleTelegram(@Body() body: any, @Req() req: any) {
    try {
      return await this.webhookService.processTelegramWebhook(body, req.user);
    } catch (error) {
      throw new BadRequestException('Invalid Telegram webhook payload');
    }
  }

  @Post('wechat')
  @UseGuards(new AuthGuard('webhook:write'))
  async handleWeChat(@Body() body: any, @Headers() headers: any, @Req() req: any) {
    try {
      return await this.webhookService.processWeChatWebhook(body, headers, req.user);
    } catch (error) {
      throw new BadRequestException('Invalid WeChat webhook payload');
    }
  }

  @Post('line')
  @UseGuards(new AuthGuard('webhook:write'))
  async handleLine(@Body() body: any, @Headers() headers: any, @Req() req: any) {
    try {
      return await this.webhookService.processLineWebhook(body, headers, req.user);
    } catch (error) {
      throw new BadRequestException('Invalid LINE webhook payload');
    }
  }
}
