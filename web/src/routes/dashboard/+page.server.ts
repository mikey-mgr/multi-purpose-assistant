import { redirect } from '@sveltejs/kit';
import { and, desc, eq, inArray, isNull, or, sql } from 'drizzle-orm';
import { getDb } from '../../lib/server/db';
import { documents, jobMatches, jobs, profiles, whatsappPilot } from '../../lib/server/db/schema';
import { publicSummary } from '../../lib/server/sanitize';

const ATTENTION_STATUSES = ['matched', 'generated'] as const;

function reasonsFrom(value: string | null): string[] {
	const cleaned = (value ?? '').replace(/\s+/g, ' ').trim();
	if (!cleaned) return ['No match notes yet.'];
	const parts = cleaned
		.split(/(?<=[.!?])\s+/)
		.map((part) => part.trim())
		.filter(Boolean)
		.slice(0, 3);
	return parts.length ? parts : [cleaned];
}

function readiness(profile: typeof profiles.$inferSelect | undefined): number {
	if (!profile) return 0;
	let score = 0;
	if (profile.headline) score += 25;
	if (profile.location) score += 15;
	if (profile.yearsExperience > 0) score += 20;
	if (profile.targetFamilies.length > 0) score += 20;
	if (profile.matchMode) score += 20;
	return Math.min(100, score);
}

export const load = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');

	const userId = locals.user.id;
	const db = await getDb();

	const [profile, matchRows, statusRows, docRows, docCountRows, pilotRows, pilotCountRows] = await Promise.all([
		db.select().from(profiles).where(eq(profiles.userId, userId)).limit(1),
		db
			.select({
				matchId: jobMatches.id,
				status: jobMatches.status,
				score: jobMatches.score,
				reason: jobMatches.reason,
				createdAt: jobMatches.createdAt,
				jobId: jobs.publicId,
				title: jobs.title,
				company: jobs.company,
				location: jobs.location,
				jobType: jobs.jobType,
				compensation: jobs.compensation,
				datePosted: jobs.datePosted
			})
			.from(jobMatches)
			.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
			.where(
				and(
					eq(jobMatches.userId, userId),
					inArray(jobMatches.status, ATTENTION_STATUSES),
					or(isNull(jobs.expires), sql`${jobs.expires} >= current_date`)
				)
			)
			.orderBy(desc(jobMatches.createdAt), desc(jobMatches.score))
			.limit(3),
		db
			.select({ status: jobMatches.status, count: sql<number>`count(*)::int` })
			.from(jobMatches)
			.where(eq(jobMatches.userId, userId))
			.groupBy(jobMatches.status),
		db
			.select({
				id: documents.id,
				type: documents.documentType,
				promptName: documents.promptName,
				createdAt: documents.createdAt,
				jobTitle: jobs.title,
				company: jobs.company
			})
			.from(documents)
			.leftJoin(jobs, eq(documents.jobId, jobs.id))
			.where(eq(documents.userId, userId))
			.orderBy(desc(documents.createdAt))
			.limit(2),
		db
			.select({ count: sql<number>`count(*)::int` })
			.from(documents)
			.where(eq(documents.userId, userId)),
		db
			.select()
			.from(whatsappPilot)
			.where(eq(whatsappPilot.userId, userId))
			.limit(1),
		db
			.select({ count: sql<number>`count(*)::int` })
			.from(whatsappPilot)
			.where(eq(whatsappPilot.status, 'active'))
	]);

	const counts = new Map(statusRows.map((row) => [row.status, row.count]));
	const applied = counts.get('applied') ?? 0;
	const newMatches = (counts.get('matched') ?? 0) + (counts.get('generated') ?? 0);
	const totalMatches = statusRows.reduce((sum, row) => sum + row.count, 0);
	const docTotal = docCountRows[0]?.count ?? 0;

	const matches = matchRows.map((row) => ({
		id: row.jobId,
		title: row.title ?? 'Untitled role',
		company: row.company ?? 'Employer',
		location: row.location ?? 'Zimbabwe',
		salary: row.compensation ?? undefined,
		type: row.jobType ?? undefined,
		score: row.score ?? 0,
		summary: publicSummary(row.reason),
		reasons: reasonsFrom(row.reason),
		skills: [],
		gaps: [],
		href: '/dashboard'
	}));

	return {
		user: locals.user,
		matches,
		preview: matches.length === 0,
		stats: {
			newMatches,
			applied,
			totalMatches,
			documents: docTotal
		},
		documents: docRows,
		pilot: {
			joined: Boolean(pilotRows[0]),
			slot: pilotRows[0]?.slot ?? null,
			status: pilotRows[0]?.status ?? null,
			phone: pilotRows[0]?.phone ?? null,
			slotsOpen: Math.max(0, 15 - (pilotCountRows[0]?.count ?? 0)),
			promptDismissed: Boolean(profile[0]?.whatsappPromptDismissedAt)
		},
		profile: {
			readiness: readiness(profile[0]),
			headline: profile[0]?.headline ?? null,
			location: profile[0]?.location ?? null,
			matchMode: profile[0]?.matchMode ?? 'balanced'
		}
	};
};
