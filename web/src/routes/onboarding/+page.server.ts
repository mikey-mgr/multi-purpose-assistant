import { fail, redirect } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { z } from 'zod';
import { getDb } from '../../lib/server/db';
import { profiles } from '../../lib/server/db/schema';
import { triggerMatchingForUser } from '../../lib/server/matching';
import { CV_TEMPLATE_VALUES } from '../../lib/cv-templates';

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

const onboardingInput = z
	.object({
		headline: z.string().trim().min(2).max(160),
		location: z.string().trim().min(2).max(120),
		yearsExperience: z.number().int().min(0).max(50),
		targetFamilies: z.array(z.enum(ROLE_FAMILIES)).max(8),
		matchMode: z.enum(['strict', 'balanced', 'broad']),
		resumeText: z.string().trim().max(20000).optional(),
		phone: z.string().trim().max(60).optional(),
		linkedinUrl: z.string().trim().max(500).optional(),
		cvTemplate: z.enum(CV_TEMPLATE_VALUES),
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
		onboardingCompleted: z.boolean()
	})
	.strict();

function parseReferences(raw: FormDataEntryValue | null) {
	const text = typeof raw === 'string' ? raw.trim() : '';
	if (!text) return undefined;
	try {
		const parsed = JSON.parse(text);
		return Array.isArray(parsed) && parsed.length ? parsed : undefined;
	} catch {
		return undefined;
	}
}

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
			resumeText: String(form.get('resumeText') ?? '').trim() || undefined,
			phone: String(form.get('phone') ?? '').trim() || undefined,
			linkedinUrl: String(form.get('linkedinUrl') ?? '').trim() || undefined,
			cvTemplate: String(form.get('cvTemplate') ?? 'harvard'),
			references: parseReferences(form.get('referencesJson')),
			referencesEnabled: form.get('referencesEnabled') === 'on',
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

		await triggerMatchingForUser({
			userId: locals.user.id,
			matchSince: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
		});

		redirect(303, '/dashboard');
	}
};
