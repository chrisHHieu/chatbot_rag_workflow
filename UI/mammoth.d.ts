declare module 'mammoth' {
  export interface ConvertToHtmlOptions {
    arrayBuffer: ArrayBuffer;
  }

  export interface ConversionMessage {
    type: string;
    message: string;
  }

  export interface ConversionResult {
    value: string;
    messages: ConversionMessage[];
  }

  export function convertToHtml(options: ConvertToHtmlOptions): Promise<ConversionResult>;
}

