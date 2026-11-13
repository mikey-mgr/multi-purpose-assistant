import { envValue } from './env';

const DEFAULT_MODEL = 'gemini-3.5-flash-lite';
const ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions';

export async function generateText(
	prompt: string,
	temperature = 0.35,
	maxTokens = 1800
): Promise<string | null> {
	return request([{ role: 'user', content: prompt }], temperature, maxTokens);
}

export async function generateTextWithImage(
	prompt: string,
	imageBase64: string,
	mimetype: string,
	temperature = 0.2,
	maxTokens = 3000
): Promise<string | null> {
	return request(
		[
			{
				role: 'user',
				content: [
					{ type: 'text', text: prompt },
					{ type: 'image_url', image_url: { url: `data:${mimetype};base64,${imageBase64}` } }
				]
			}
		],
		temperature,
		maxTokens
	);
}

/**
 * Every configured key, primary first.
 *
 * Both keys are the same account tier in practice, so a single request rotates
 * through them on any rate-limit or quota failure (RPM, TPM or RPD).
 */
function apiKeys(): string[] {
	const keys = [envValue('GEMINI_API_KEY'), envValue('SECONDARY_GEMINI_API_KEY')]
		.map((value) => value?.trim())
		.filter((value): value is string => Boolean(value));
	return [...new Set(keys)];
}

/** Status codes that mean "this key is exhausted", not "this request is bad". */
const RETRYABLE = new Set([401, 403, 408, 425, 429, 500, 502, 503, 504]);

/** A 400 is retryable only when the body blames the key itself. */
function blamesKey(text: string): boolean {
	return /api[\s_-]?key|permission|quota|billing|credential|expired/i.test(text);
}

async function request(
	messages: unknown[],
	temperature: number,
	maxTokens: number
): Promise<string | null> {
	const keys = apiKeys();
	if (keys.length === 0) return null;

	const model = envValue('GEMINI_MODEL') ?? DEFAULT_MODEL;
	const timeoutMs = maxTokens > 4000 ? 90000 : 25000;

	for (let index = 0; index < keys.length; index += 1) {
		const key = keys[index];
		const isLastKey = index === keys.length - 1;
		try {
			const response = await fetch(ENDPOINT, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${key}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					model,
					messages,
					temperature,
					max_tokens: maxTokens
				}),
				signal: AbortSignal.timeout(timeoutMs)
			});

			if (response.ok) {
				const payload = (await response.json()) as {
					choices?: Array<{ message?: { content?: string } }>;
				};
				return payload.choices?.[0]?.message?.content?.trim() || null;
			}

			let detail = '';
			if (response.status === 400) {
				detail = await response.text().catch(() => '');
			}
			const keyFailure =
				RETRYABLE.has(response.status) ||
				(response.status === 400 && blamesKey(detail));

			if (!keyFailure || isLastKey) {
				// A genuinely malformed request fails the same way on every key.
				return null;
			}
			console.warn(
				`Gemini key ${index + 1}/${keys.length} failed (${response.status}); trying the next key`
			);
		} catch (error) {
			if (isLastKey) return null;
			console.warn(
				`Gemini key ${index + 1}/${keys.length} failed: ${
					error instanceof Error ? error.message : String(error)
				}; trying the next key`
			);
		}
	}

	return null;
}
