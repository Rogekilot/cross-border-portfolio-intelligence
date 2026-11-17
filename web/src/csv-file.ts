import { ApiError } from './transport';

export const CSV_FILE_LIMIT = 16_384;
export const CSV_ENVELOPE_LIMIT = 32_768;

/** Preserve selected bytes. CSV decoding and interpretation belong to the server. */
export async function csvFileBytes(file: Pick<File, 'name' | 'size' | 'arrayBuffer'>): Promise<{ name: string; base64: string; byteLength: number }> {
  if (file.size === 0) throw new ApiError('CSV_EMPTY_FILE', 'Choose a nonempty fictional CSV file');
  if (file.size > CSV_FILE_LIMIT) throw new ApiError('CSV_FILE_TOO_LARGE', 'The raw file limit is 16384 bytes', 413);
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes.byteLength !== file.size || bytes.byteLength > CSV_FILE_LIMIT) throw new ApiError('CSV_FILE_TOO_LARGE', 'The selected file changed or exceeds the byte limit', 413);
  return { name: file.name, base64: btoa(String.fromCharCode(...bytes)), byteLength: bytes.byteLength };
}

export function csvEnvelopeBytes(value: unknown): number { return new TextEncoder().encode(JSON.stringify(value)).byteLength; }
export function assertCsvEnvelope(value: unknown): void {
  if (csvEnvelopeBytes(value) > CSV_ENVELOPE_LIMIT) throw new ApiError('CSV_REQUEST_TOO_LARGE', 'The complete UTF-8 JSON request exceeds 32768 bytes', 413);
}

/** Downloads originate from the authenticated response, never an external URL. */
export function downloadCsvArtifact(content: string, filename: string, format: 'CSV' | 'JSON'): void {
  if (!/^finweb-[a-zA-Z0-9._-]+\.(?:csv|json)$/.test(filename) || filename.length > 160
    || !filename.endsWith(format === 'CSV' ? '.csv' : '.json')) throw new ApiError('INVALID_RESPONSE', 'Unsafe export filename');
  const url = URL.createObjectURL(new Blob([content], { type: format === 'CSV' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.hidden = true;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
