import { fail, redirect } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { z } from 'zod';
import { getDb } from '../../lib/server/db';
import { profiles } from '../../lib/server/db/schema';

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

const onboardingInput = z
	.object({
		headline: z.string().trim().min(2).max(160),
		location: z.string().trim().min(2).max(120),
		yearsExperience: z.number().int().min(0).max(50),
		targetFamilies: z.array(z.enum(ROLE_FAMILIES)).max(8),
		matchMode: z.enum(['strict', 'balanced', 'broad']),
		onboardingCompleted: z.boolean()
	})
	.strict();

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');

	const db = await getDb();
	const existing = await db
		.select()
		.from(profiles)
		.where(eq(profiles.userId, locals.user.id))
		.limit(1);

	return { user: locals.user, profile: existing[0] ?? null };
};

export const actions = {
	default: async ({ request, locals }) => {
		if (!locals.user) redirect(303, '/login');

		const form = await request.formData();
		const raw = {
			headline: String(form.get('headline') ?? '').trim(),
			location: String(form.get('location') ?? '').trim(),
			yearsExperience: Number(form.get('yearsExperience') ?? 0),
			targetFamilies: form.getAll('targetFamilies').map(String),
			matchMode: String(form.get('matchMode') ?? 'balanced'),
			onboardingCompleted: true
		};

		const parsed = onboardingInput.safeParse(raw);
		if (!parsed.success) {
			return fail(400, {
				error: 'Please check the highlighted fields.',
				values: raw
			});
		}

		const db = await getDb();
		const updatedAt = new Date();
		await db
			.insert(profiles)
			.values({
				userId: locals.user.id,
				...parsed.data,
				matchSince: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
				updatedAt
			})
			.onConflictDoUpdate({
				target: profiles.userId,
				set: { ...parsed.data, updatedAt }
			});

		redirect(303, '/dashboard');
	}
};
