import { envValue } from './env';

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function toBase64(bytes: Uint8Array): string {
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary);
}

function fromBase64(value: string): Uint8Array {
	const binary = atob(value);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
	return bytes;
}

export function base64Url(bytes: Uint8Array | string): string {
	const input = typeof bytes === 'string' ? encoder.encode(bytes) : bytes;
	return toBase64(input).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

export function randomToken(byteLength = 32): string {
	const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
	return base64Url(bytes);
}

async function encryptionKey(): Promise<CryptoKey> {
	const encoded = envValue('TOKEN_ENCRYPTION_KEY');
	if (!encoded) {
		throw new Error('TOKEN_ENCRYPTION_KEY is not configured');
	}
	const raw = fromBase64(encoded);
	if (raw.byteLength !== 32) {
		throw new Error('TOKEN_ENCRYPTION_KEY must be 32 bytes, base64 encoded');
	}
	return crypto.subtle.importKey('raw', raw as BufferSource, { name: 'AES-GCM' }, false, [
		'encrypt',
		'decrypt'
	]);
}

export async function encryptSecret(plaintext: string): Promise<{ ciphertext: string; iv: string }> {
	const iv = crypto.getRandomValues(new Uint8Array(12));
	const key = await encryptionKey();
	const encrypted = await crypto.subtle.encrypt(
		{ name: 'AES-GCM', iv: iv as BufferSource },
		key,
		encoder.encode(plaintext)
	);
	return { ciphertext: toBase64(new Uint8Array(encrypted)), iv: toBase64(iv) };
}

export async function decryptSecret(ciphertext: string, iv: string): Promise<string> {
	const key = await encryptionKey();
	const decrypted = await crypto.subtle.decrypt(
		{ name: 'AES-GCM', iv: fromBase64(iv) as BufferSource },
		key,
		fromBase64(ciphertext) as BufferSource
	);
	return decoder.decode(decrypted);
}

export async function sha512Hex(value: string): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-512', encoder.encode(value));
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('')
		.toUpperCase();
}

export async function sha256Hex(value: string): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-256', encoder.encode(value));
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('');
}

export function timingSafeEqual(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let mismatch = 0;
	for (let i = 0; i < a.length; i += 1) {
		mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
	}
	return mismatch === 0;
}
