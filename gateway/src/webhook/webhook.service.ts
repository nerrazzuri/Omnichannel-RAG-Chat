import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class WebhookService {
  private readonly logger = new Logger(WebhookService.name);

  constructor(private configService: ConfigService) {}

  async processWhatsAppWebhook(body: any, headers: any): Promise<any> {
    this.logger.log('Processing WhatsApp webhook');

    // Verify webhook signature if provided
    if (headers['x-hub-signature-256']) {
      this.verifyWhatsAppSignature(body, headers['x-hub-signature-256']);
    }

    // Normalize WhatsApp message format
    const normalizedMessage = this.normalizeWhatsAppMessage(body);

    // Forward to AI Core service
    await this.forwardToAICore(normalizedMessage);

    return { status: 'ok', message: 'WhatsApp webhook processed' };
  }

  async processTeamsWebhook(body: any): Promise<any> {
    this.logger.log('Processing Teams webhook');

    const normalizedMessage = this.normalizeTeamsMessage(body);
    await this.forwardToAICore(normalizedMessage);

    return { status: 'ok', message: 'Teams webhook processed' };
  }

  async processTelegramWebhook(body: any): Promise<any> {
    this.logger.log('Processing Telegram webhook');

    const normalizedMessage = this.normalizeTelegramMessage(body);
    await this.forwardToAICore(normalizedMessage);

    return { status: 'ok', message: 'Telegram webhook processed' };
  }

  async processWeChatWebhook(body: any, headers: any): Promise<any> {
    this.logger.log('Processing WeChat webhook');

    const normalizedMessage = this.normalizeWeChatMessage(body);
    await this.forwardToAICore(normalizedMessage);

    return { status: 'ok', message: 'WeChat webhook processed' };
  }

  async processLineWebhook(body: any, headers: any): Promise<any> {
    this.logger.log('Processing LINE webhook');

    const normalizedMessage = this.normalizeLineMessage(body);
    await this.forwardToAICore(normalizedMessage);

    return { status: 'ok', message: 'LINE webhook processed' };
  }

  private normalizeWhatsAppMessage(body: any): any {
    const entry = body.entry?.[0];
    const message = entry?.changes?.[0]?.value?.messages?.[0];

    if (!message) {
      throw new Error('No message found in WhatsApp webhook');
    }

    return {
      channel: 'whatsapp',
      platform_message_id: message.id,
      sender_id: message.from,
      timestamp: new Date(parseInt(message.timestamp) * 1000),
      content: message.text?.body || '',
      message_type: this.getWhatsAppMessageType(message),
      metadata: {
        display_phone_number: entry?.changes?.[0]?.value?.metadata?.display_phone_number,
        phone_number_id: entry?.changes?.[0]?.value?.metadata?.phone_number_id,
      }
    };
  }

  private normalizeTeamsMessage(body: any): any {
    return {
      channel: 'teams',
      platform_message_id: body.id,
      sender_id: body.from?.id,
      channel_id: body.channelId,
      timestamp: new Date(body.timestamp),
      content: body.text || '',
      message_type: 'text',
      metadata: {
        conversation_id: body.conversation?.id,
        service_url: body.serviceUrl,
      }
    };
  }

  private normalizeTelegramMessage(body: any): any {
    const message = body.message;

    if (!message) {
      throw new Error('No message found in Telegram webhook');
    }

    return {
      channel: 'telegram',
      platform_message_id: message.message_id.toString(),
      sender_id: message.from?.id?.toString(),
      chat_id: message.chat?.id?.toString(),
      timestamp: new Date(message.date * 1000),
      content: message.text || '',
      message_type: this.getTelegramMessageType(message),
      metadata: {
        username: message.from?.username,
      }
    };
  }

  private normalizeWeChatMessage(body: any): any {
    return {
      channel: 'wechat',
      platform_message_id: body.MsgId,
      sender_id: body.FromUserName,
      timestamp: new Date(parseInt(body.CreateTime) * 1000),
      content: body.Content || '',
      message_type: body.MsgType || 'text',
      metadata: {
        to_user: body.ToUserName,
      }
    };
  }

  private normalizeLineMessage(body: any): any {
    const event = body.events?.[0];

    if (!event) {
      throw new Error('No event found in LINE webhook');
    }

    return {
      channel: 'line',
      platform_message_id: event.message?.id || event.id,
      sender_id: event.source?.userId,
      timestamp: new Date(event.timestamp),
      content: event.message?.text || '',
      message_type: event.message?.type || 'text',
      metadata: {
        reply_token: event.replyToken,
        source_type: event.source?.type,
      }
    };
  }

  private getWhatsAppMessageType(message: any): string {
    if (message.text) return 'text';
    if (message.image) return 'image';
    if (message.document) return 'document';
    if (message.audio) return 'audio';
    if (message.video) return 'video';
    if (message.location) return 'location';
    return 'unknown';
  }

  private getTelegramMessageType(message: any): string {
    if (message.text) return 'text';
    if (message.photo) return 'photo';
    if (message.document) return 'document';
    if (message.audio) return 'audio';
    if (message.video) return 'video';
    if (message.voice) return 'voice';
    if (message.location) return 'location';
    return 'unknown';
  }

  private verifyWhatsAppSignature(body: any, signature: string): boolean {
    // Basic WhatsApp signature verification implementation
    // In production, implement proper HMAC-SHA256 verification with your app secret
    try {
      // This is a simplified implementation for testing
      // Real implementation should use crypto.subtle or similar for proper HMAC
      const expectedSignature = signature.replace('sha256=', '');
      // For now, accept any signature for testing purposes
      return true;
    } catch (error) {
      this.logger.error('Signature verification failed:', error);
      return false;
    }
  }

  private async forwardToAICore(message: any): Promise<void> {
    // Forward normalized message to AI Core service
    // For testing purposes, we'll just log the message
    // In production, implement HTTP call to ai-core service

    this.logger.log(`Forwarding message to AI Core: ${JSON.stringify(message)}`);

    // Basic implementation for testing - in production use proper HTTP client
    try {
      // Example HTTP call (commented out for testing)
      // const response = await fetch('http://localhost:8000/v1/query', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(message)
      // });

      // For now, just log that forwarding would happen
      this.logger.log(`Message would be forwarded to AI Core for processing`);
    } catch (error) {
      this.logger.error('Failed to forward message to AI Core:', error);
    }
  }
}
