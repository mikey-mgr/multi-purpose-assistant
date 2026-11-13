import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { profiles } from '../../../lib/server/db/schema';
import { triggerMatchingForUser } from '../../../lib/server/matching';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';
import { CV_TEMPLATE_VALUES } from '../../../lib/cv-templates';

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
	'finance',
	'banking',
	'hr',
	'marketing',
	'legal',
	'healthcare',
	'engineering',
	'mining',
	'agriculture',
	'logistics',
	'hospitality',
	'customer_service',
	'trades',
	'other'
] as const;

const profileInput = z
	.object({
		headline: z.string().trim().min(1).max(160).optional(),
		location: z.string().trim().min(1).max(120).optional(),
		yearsExperience: z.number().int().min(0).max(50).optional(),
		targetFamilies: z.array(z.enum(ROLE_FAMILIES)).max(8).optional(),
		matchMode: z.enum(['strict', 'balanced', 'broad']).optional(),
		resumeText: z.string().trim().max(20000).optional(),
		phone: z.string().trim().max(60).optional(),
		linkedinUrl: z.string().trim().max(500).optional(),
		cvTemplate: z.enum(CV_TEMPLATE_VALUES).optional(),
		references: z
			.array(
				z.object({
					id: z.string().max(60),
					name: z.string().trim().min(1).max(200),
					role: z.string().trim().max(200).nullable().optional(),
					organisation: z.string().trim().max(250).nullable().optional(),
					email: z.string().trim().max(250).nullable().optional(),
					phone: z.string().trim().max(60).nullable().optional()
				})
			)
			.max(6)
			.optional(),
		referencesEnabled: z.boolean().optional(),
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

	if (
		parsed.data.onboardingCompleted === true ||
		parsed.data.resumeText !== undefined ||
		parsed.data.headline !== undefined
	) {
		await triggerMatchingForUser({
			userId: event.locals.user.id,
			matchSince: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
		});
	}

	return json({ profile: result[0] ?? null });
};
