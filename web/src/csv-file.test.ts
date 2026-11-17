import { describe, expect, it, vi } from 'vitest';
import { assertCsvEnvelope, CSV_FILE_LIMIT, csvEnvelopeBytes, csvFileBytes } from './csv-file';

describe('CSV byte and request boundary', () => {
  it('preserves the exact selected BOM, quotes and newline bytes without decoding or normalizing them', async () => {
    const bytes = new Uint8Array([0xef, 0xbb, 0xbf, ...new TextEncoder().encode('symbol,note\r\nSYN-A,"fictional,\nsource"\r\n')]);
    const file = { name: 'fictional.csv', size: bytes.length, arrayBuffer: async () => bytes.buffer };
    const result = await csvFileBytes(file);
    expect(Array.from(atob(result.base64), (character) => character.charCodeAt(0))).toEqual([...bytes]);
  });
  it('rejects oversized selected files before reading their contents', async () => {
    const read = vi.fn();
    await expect(csvFileBytes({ name: 'large.csv', size: CSV_FILE_LIMIT + 1, arrayBuffer: read })).rejects.toMatchObject({ code: 'CSV_FILE_TOO_LARGE' });
    expect(read).not.toHaveBeenCalled();
  });
  it('checks the complete UTF-8 JSON envelope, including base64 and corrections', () => {
    const body = { source_base64: 'a'.repeat(21_848), corrections: [{ reason: '说明'.repeat(2000) }] };
    expect(csvEnvelopeBytes(body)).toBeGreaterThan(JSON.stringify(body).length);
    expect(() => assertCsvEnvelope(body)).toThrowError('CSV_REQUEST_TOO_LARGE');
    expect(() => assertCsvEnvelope({ source_base64: 'a'.repeat(21_848), corrections: [] })).not.toThrow();
  });
  it('rejects empty files and a byte count that differs from the selected file metadata', async () => {
    await expect(csvFileBytes({ name: 'empty.csv', size: 0, arrayBuffer: async () => new ArrayBuffer(0) })).rejects.toMatchObject({ code: 'CSV_EMPTY_FILE' });
    await expect(csvFileBytes({ name: 'changed.csv', size: 3, arrayBuffer: async () => new ArrayBuffer(4) })).rejects.toMatchObject({ code: 'CSV_FILE_TOO_LARGE' });
  });
});
