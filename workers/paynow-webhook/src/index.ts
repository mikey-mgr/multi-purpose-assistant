type Env = {
	PAYNOW_INTEGRATION_KEY: string;
	MUKANA_WEBHOOK_URL: string;
};

type Entry = [string, string];

async function sha512Hex(value: string): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-512', new TextEncoder().encode(value));
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('')
		.toUpperCase();
}

function timingSafeEqual(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let mismatch = 0;
	for (let i = 0; i < a.length; i += 1) {
		mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
	}
	return mismatch === 0;
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		if (request.method !== 'POST') {
			return new Response('Method not allowed', { status: 405 });
		}

		let form: FormData;
		try {
			form = await request.formData();
		} catch {
			return new Response('Invalid form body', { status: 400 });
		}

		const entries: Entry[] = [];
		for (const [key, value] of form.entries()) {
			if (typeof value === 'string') entries.push([key, value]);
		}

		const hashEntry = entries.find(([key]) => key.toLowerCase() === 'hash');
		if (!hashEntry) {
			return new Response('Missing hash', { status: 400 });
		}

		const values = entries
			.filter(([key]) => key.toLowerCase() !== 'hash')
			.map(([, value]) => value);
		const expected = await sha512Hex(`${values.join('')}${env.PAYNOW_INTEGRATION_KEY}`);

		if (!timingSafeEqual(expected, hashEntry[1].toUpperCase())) {
			return new Response('Invalid hash', { status: 400 });
		}

		if (!env.MUKANA_WEBHOOK_URL) {
			return new Response('Webhook target not configured', { status: 500 });
		}

		const response = await fetch(env.MUKANA_WEBHOOK_URL, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ entries })
		});

		return new Response(await response.text(), { status: response.status });
	}
};
