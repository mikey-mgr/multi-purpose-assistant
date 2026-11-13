import { randomToken, sha512Hex, timingSafeEqual } from './crypto';
import { envValue } from './env';

const INITIATE_URL = 'https://www.paynow.co.zw/interface/initiatetransaction';

export type PaynowInitResult = {
	ok: boolean;
	status: string;
	browserUrl: string | null;
	pollUrl: string | null;
	instructions: string | null;
	error: string | null;
	raw: Record<string, string>;
};

export function isPaynowMock(): boolean {
	const mode = envValue('PAYNOW_MODE') ?? 'mock';
	return mode === 'mock';
}

export function paynowConfigured(): boolean {
	if (isPaynowMock()) return Boolean(envValue('PAYNOW_INTEGRATION_KEY'));
	return Boolean(envValue('PAYNOW_INTEGRATION_ID') && envValue('PAYNOW_INTEGRATION_KEY'));
}

export function paynowAuthEmail(customerEmail: string): string {
	return envValue('PAYNOW_AUTH_EMAIL') || customerEmail;
}

function integrationKey(): string {
	const key = envValue('PAYNOW_INTEGRATION_KEY');
	if (!key) throw new Error('PAYNOW_INTEGRATION_KEY is not configured');
	return key;
}

async function hashFields(values: string[]): Promise<string> {
	return sha512Hex(`${values.join('')}${integrationKey()}`);
}

function amountString(cents: number): string {
	return (cents / 100).toFixed(2);
}

export function newPaymentReference(): string {
	return `MK-${Date.now().toString(36).toUpperCase()}-${randomToken(6).toUpperCase()}`;
}

export async function initiatePaynowPayment(input: {
	reference: string;
	amountCents: number;
	additionalInfo: string;
	email?: string | null;
	phone?: string | null;
}): Promise<PaynowInitResult> {
	const returnUrl =
		envValue('PAYNOW_RETURN_URL') ?? 'http://127.0.0.1:4173/billing/success';
	const resultUrl =
		envValue('PAYNOW_RESULT_URL') ?? 'http://127.0.0.1:4173/api/webhooks/paynow';

	if (isPaynowMock()) {
		return {
			ok: true,
			status: 'Ok',
			browserUrl: `/billing/mock?reference=${encodeURIComponent(input.reference)}`,
			pollUrl: 'mock-poll-url',
			instructions: 'Mock checkout. Use the mock payment button to complete.',
			error: null,
			raw: {
				status: 'Ok',
				browserurl: `/billing/mock?reference=${encodeURIComponent(input.reference)}`,
				pollurl: 'mock-poll-url'
			}
		};
	}

	const id = envValue('PAYNOW_INTEGRATION_ID');
	if (!id) throw new Error('PAYNOW_INTEGRATION_ID is not configured');

	const fields: Array<[string, string]> = [
		['id', id],
		['reference', input.reference],
		['amount', amountString(input.amountCents)],
		['additionalinfo', input.additionalInfo],
		['returnurl', returnUrl],
		['resulturl', resultUrl],
		['status', 'Message']
	];

	if (input.email) fields.push(['authemail', input.email]);
	if (input.phone) fields.push(['authphone', input.phone]);

	const hash = await hashFields(fields.map(([, value]) => value));
	const body = new URLSearchParams();
	for (const [key, value] of fields) body.set(key, value);
	body.set('hash', hash);

	const response = await fetch(INITIATE_URL, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: body.toString()
	});

	const text = await response.text();
	const parsed = new URLSearchParams(text);
	const responseEntries = Array.from(parsed.entries()) as Array<[string, string]>;
	const raw: Record<string, string> = {};
	for (const [key, value] of responseEntries) raw[key.toLowerCase()] = value;

	if (raw.status?.toLowerCase() === 'error') {
		return {
			ok: false,
			status: 'Error',
			browserUrl: null,
			pollUrl: null,
			instructions: null,
			error: raw.error ?? 'Paynow rejected the transaction',
			raw
		};
	}

	const validHash = await verifyPaynowEntries(responseEntries);
	if (!validHash) {
		return {
			ok: false,
			status: 'Error',
			browserUrl: null,
			pollUrl: null,
			instructions: null,
			error: 'Paynow response failed hash verification',
			raw
		};
	}

	return {
		ok: raw.status?.toLowerCase() === 'ok',
		status: raw.status ?? 'Unknown',
		browserUrl: raw.browserurl ?? null,
		pollUrl: raw.pollurl ?? null,
		instructions: raw.instructions ?? null,
		error: null,
		raw
	};
}

export async function verifyPaynowEntries(entries: Array<[string, string]>): Promise<boolean> {
	const hashEntry = entries.find(([key]) => key.toLowerCase() === 'hash');
	if (!hashEntry) return false;

	const values = entries
		.filter(([key]) => key.toLowerCase() !== 'hash')
		.map(([, value]) => value);
	const expected = await hashFields(values);
	return timingSafeEqual(expected, hashEntry[1].toUpperCase());
}

export async function verifyPaynowHash(formData: FormData): Promise<boolean> {
	const entries = Array.from(formData.entries()).filter(
		(entry): entry is [string, string] => typeof entry[1] === 'string'
	);
	return verifyPaynowEntries(entries);
}

export function paynowFormObject(formData: FormData): Record<string, string> {
	const raw: Record<string, string> = {};
	for (const [key, value] of formData.entries()) {
		if (typeof value === 'string') raw[key.toLowerCase()] = value;
	}
	return raw;
}
