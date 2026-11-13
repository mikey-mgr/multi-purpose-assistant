import { Container } from '@cloudflare/containers';

interface Env {
	MATCHER: DurableObjectNamespace;
	MATCH_TRIGGER_SECRET: string;
	DATABASE_URL: string;
	GEMINI_API_KEY: string;
}

function constantTimeEqual(a: string, b: string): boolean {
	if (a.length !== b.length) return false;
	let mismatch = 0;
	for (let i = 0; i < a.length; i += 1) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
	return mismatch === 0;
}

export class MatcherContainer extends Container {
	defaultPort = 8000;
	sleepAfter = '10m';
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		if (url.pathname !== '/match' && url.pathname !== '/generate') {
			return new Response('Not found', { status: 404 });
		}
		if (request.method !== 'POST') {
			return new Response('Method not allowed', { status: 405 });
		}

		const supplied = request.headers.get('x-match-trigger-secret') ?? '';
		if (!env.MATCH_TRIGGER_SECRET || !constantTimeEqual(supplied, env.MATCH_TRIGGER_SECRET)) {
			return Response.json({ error: 'Unauthorized' }, { status: 401 });
		}
		if (!env.DATABASE_URL || !env.GEMINI_API_KEY) {
			return Response.json({ error: 'Matcher secrets are not configured' }, { status: 503 });
		}

		const headers = new Headers();
		headers.set('content-type', 'application/json');
		headers.set('x-database-url', env.DATABASE_URL);
		headers.set('x-gemini-key', env.GEMINI_API_KEY);
		headers.set('x-match-trigger-secret', env.MATCH_TRIGGER_SECRET);
		const body = await request.text();

		const container = env.MATCHER.get(env.MATCHER.idFromName('matcher'));
		return container.fetch(
			new Request(`http://container${url.pathname}`, {
				method: 'POST',
				headers,
				body
			})
		);
	}
};
