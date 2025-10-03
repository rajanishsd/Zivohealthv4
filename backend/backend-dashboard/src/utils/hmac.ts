import CryptoJS from 'crypto-js';

export interface HMACHeaders {
  'X-Timestamp': string;
  'X-App-Signature': string;
}

export class HMACGenerator {
  private appSecret: string;

  constructor(appSecret: string) {
    this.appSecret = appSecret;
  }

  /**
   * Generate HMAC signature for request authentication
   */
  generateSignature(payload: string, timestamp: string): string {
    const message = `${payload}.${timestamp}`;
    return CryptoJS.HmacSHA256(message, this.appSecret).toString();
  }

  /**
   * Generate HMAC headers for a request
   */
  generateHeaders(payload: string): HMACHeaders {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signature = this.generateSignature(payload, timestamp);
    
    return {
      'X-Timestamp': timestamp,
      'X-App-Signature': signature
    };
  }

  /**
   * Generate HMAC headers for JSON payload
   */
  generateJSONHeaders(jsonPayload: any): HMACHeaders {
    const payload = JSON.stringify(jsonPayload);
    console.log('HMAC DEBUG: Generating headers for payload:', payload);
    console.log('HMAC DEBUG: Secret key length:', this.appSecret.length);
    const headers = this.generateHeaders(payload);
    console.log('HMAC DEBUG: Generated headers:', headers);
    return headers;
  }
}

// Create a singleton instance
const appSecret = process.env.REACT_APP_SECRET_KEY || '';
console.log('HMAC Generator initialized with secret key length:', appSecret.length);
export const hmacGenerator = new HMACGenerator(appSecret);
