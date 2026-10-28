import { and, eq, sql } from 'drizzle-orm';
import type { RequestEvent } from '@sveltejs/kit';
import { getDb } from './db';
import { apiRateLimits } from './db/schema';

export type RateLimitResult = {
	allowed: boolean;
	limit: number;
	remaining: number;
	retryAfter: number;
};

export function rateLimitKey(event: RequestEvent, scope: string): string {
	const identity = event.locals.user?.id ?? event.getClientAddress();
	return `${scope}:${identity}`;
}

export async function rateLimit(
	key: string,
	limit: number,
	windowSeconds: number
): Promise<RateLimitResult> {
	const now = Date.now();
	const windowMs = windowSeconds * 1000;
	const windowStart = new Date(Math.floor(now / windowMs) * windowMs);
	const db = await getDb();

	await db
		.insert(apiRateLimits)
		.values({ key, windowStart, count: 1 })
		.onConflictDoUpdate({
			target: [apiRateLimits.key, apiRateLimits.windowStart],
			set: { count: sql`${apiRateLimits.count} + 1` }
		});

	const rows = await db
		.select({ count: apiRateLimits.count })
		.from(apiRateLimits)
		.where(and(eq(apiRateLimits.key, key), eq(apiRateLimits.windowStart, windowStart)))
		.limit(1);

	const count = rows[0]?.count ?? 1;
	const retryAfter = Math.max(
		1,
		windowSeconds - Math.floor((now - windowStart.getTime()) / 1000)
	);

	return {
		allowed: count <= limit,
		limit,
		remaining: Math.max(0, limit - count),
		retryAfter
	};
}

export function tooManyRequests(result: RateLimitResult): Response {
	return new Response(JSON.stringify({ error: 'Too many requests' }), {
		status: 429,
		headers: {
			'Content-Type': 'application/json',
			'Retry-After': String(result.retryAfter),
			'X-RateLimit-Limit': String(result.limit),
			'X-RateLimit-Remaining': '0'
		}
	});
}
