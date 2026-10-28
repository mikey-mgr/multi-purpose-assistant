import type { Handle } from '@sveltejs/kit/hooks';
import { getAuth } from './lib/server/auth';
import { setRuntimeEnv } from './lib/server/env';

const baseHeaders: Record<string, string> = {
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
	'X-Frame-Options': 'DENY',
	'Cross-Origin-Opener-Policy': 'same-origin-allow-popups',
	'Cross-Origin-Embedder-Policy': 'credentialless',
	'Cross-Origin-Resource-Policy': 'same-origin',
	'X-Permitted-Cross-Domain-Policies': 'none'
};

export const handle: Handle = async ({ event, resolve }) => {
	if (import.meta.env.DEV && typeof process !== 'undefined' && !process.env.DATABASE_URL) {
		await import('dotenv/config');
	}

	setRuntimeEnv(event.platform?.env as unknown as Record<string, string | undefined>);

	const mutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(event.request.method);
	const contentType = event.request.headers.get('content-type') ?? '';
	const isForm =
		contentType.includes('application/x-www-form-urlencoded') ||
		contentType.includes('multipart/form-data') ||
		contentType.includes('text/plain');
	const isWebhook = event.url.pathname.startsWith('/api/webhooks/');

	if (mutating && isForm && !isWebhook) {
		const origin = event.request.headers.get('origin');
		if (origin && origin !== event.url.origin) {
			return new Response('Cross-site form submissions are forbidden', { status: 403 });
		}
	}

	event.locals.user = null;
	event.locals.session = null;

	const cookie = event.request.headers.get('cookie');
	if (cookie?.includes('better-auth')) {
		try {
			const auth = await getAuth();
			const result = await auth.api.getSession({ headers: event.request.headers });
			event.locals.user = result?.user ?? null;
			event.locals.session = result?.session ?? null;
		} catch {
			event.locals.user = null;
			event.locals.session = null;
		}
	}

	const response = await resolve(event);

	for (const [key, value] of Object.entries(baseHeaders)) {
		response.headers.set(key, value);
	}

	const secure = event.url.protocol === 'https:';
	const csp = [
		"default-src 'self'",
		"script-src 'self' 'unsafe-inline'",
		"style-src 'self' 'unsafe-inline'",
		"img-src 'self' data:",
		"font-src 'self'",
		"connect-src 'self'",
		"frame-ancestors 'none'",
		"base-uri 'self'",
		"form-action 'self'",
		"object-src 'none'",
		...(secure ? ['upgrade-insecure-requests'] : [])
	].join('; ');

	response.headers.set('Content-Security-Policy', csp);

	if (secure) {
		response.headers.set(
			'Strict-Transport-Security',
			'max-age=31536000; includeSubDomains; preload'
		);
	}

	return response;
};
