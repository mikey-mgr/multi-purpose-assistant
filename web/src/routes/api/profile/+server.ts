import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { profiles } from '../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

const ROLE_FAMILIES = [
	'software',
	'data',
	'it_support',
	'cyber',
	'sales',
	'teaching',
	'compliance',
	'electronics',
	'admin',
	'other'
] as const;

const profileInput = z
	.object({
		headline: z.string().trim().min(1).max(160).optional(),
		location: z.string().trim().min(1).max(120).optional(),
		yearsExperience: z.number().int().min(0).max(50).optional(),
		targetFamilies: z.array(z.enum(ROLE_FAMILIES)).max(8).optional(),
		matchMode: z.enum(['strict', 'balanced', 'broad']).optional(),
		onboardingCompleted: z.boolean().optional()
	})
	.strict();

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'profile:get'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const profile = await db
		.select()
		.from(profiles)
		.where(eq(profiles.userId, event.locals.user.id))
		.limit(1);

	return json(
		{ profile: profile[0] ?? null },
		{
			headers: {
				'Cache-Control': 'no-store',
				'X-RateLimit-Limit': String(limit.limit),
				'X-RateLimit-Remaining': String(limit.remaining)
			}
		}
	);
};

export const PATCH: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'profile:patch'), 30, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = profileInput.safeParse(body);
	if (!parsed.success) {
		return json(
			{ error: 'Invalid profile', issues: parsed.error.flatten() },
			{ status: 400 }
		);
	}

	const data = Object.fromEntries(
		Object.entries(parsed.data).filter(([, value]) => value !== undefined)
	);

	if (Object.keys(data).length === 0) {
		return json({ error: 'No fields to update' }, { status: 400 });
	}

	const db = await getDb();
	const updatedAt = new Date();
	const result = await db
		.insert(profiles)
		.values({
			userId: event.locals.user.id,
			...data,
			matchSince: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
		})
		.onConflictDoUpdate({
			target: profiles.userId,
			set: { ...data, updatedAt }
		})
		.returning();

	return json({ profile: result[0] ?? null });
};
