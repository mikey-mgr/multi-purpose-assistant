import { error, redirect } from '@sveltejs/kit';
import { and, desc, eq } from 'drizzle-orm';
import { decodedBase64Size } from '../../../lib/server/application-kit';
import { getDb } from '../../../lib/server/db';
import {
	applicationKits,
	documents,
	jobMatches,
	jobs,
	profiles,
	userFiles
} from '../../../lib/server/db/schema';
import { matchesFile } from '../../../lib/server/resume/kit';
import { envValue } from '../../../lib/server/env';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const load = async ({ locals, params }) => {
	if (!locals.user) redirect(303, '/login');
	if (!UUID_RE.test(params.id)) error(404, 'Match not found');

	const userId = locals.user.id;
	const db = await getDb();
	const rows = await db
		.select({
			matchId: jobMatches.id,
			status: jobMatches.status,
			score: jobMatches.score,
			reason: jobMatches.reason,
			proceed: jobMatches.proceed,
			requiredDocs: jobMatches.requiredDocs,
			applyRecipient: jobMatches.applyRecipient,
			applySubject: jobMatches.applySubject,
			jobId: jobs.id,
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			jobType: jobs.jobType,
			compensation: jobs.compensation,
			expires: jobs.expires,
			sourceUrl: jobs.sourceUrl
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(and(eq(jobMatches.id, params.id), eq(jobMatches.userId, userId)))
		.limit(1);

	const match = rows[0];
	if (!match) error(404, 'Match not found');

	const [kitRows, documentRows, fileRows, profileRows] = await Promise.all([
		db
			.select()
			.from(applicationKits)
			.where(and(eq(applicationKits.userId, userId), eq(applicationKits.jobId, match.publicId)))
			.orderBy(desc(applicationKits.createdAt))
			.limit(1),
		db
			.select({
				id: documents.id,
				type: documents.documentType,
				createdAt: documents.createdAt
			})
			.from(documents)
			.where(and(eq(documents.userId, userId), eq(documents.jobId, match.jobId)))
			.orderBy(desc(documents.createdAt)),
		db.select().from(userFiles).where(eq(userFiles.userId, userId)),
		db
			.select({ legacyUserId: profiles.legacyUserId })
			.from(profiles)
			.where(eq(profiles.userId, userId))
			.limit(1)
	]);

	const kit = kitRows[0] ?? null;
	const required = match.requiredDocs ? (JSON.parse(match.requiredDocs) as string[]) : [];
	const missing = required.filter(
		(kind) =>
			kind !== 'cv' && kind !== 'cover_letter' && !fileRows.some((file) => matchesFile(kind, file))
	);

	const DOC_LABELS: Record<string, string> = {
		national_id: 'National ID',
		certificate: 'certificate or transcript',
		drivers_license: 'driver licence',
		document: 'supporting document'
	};

	return {
		match: {
			id: match.matchId,
			status: match.status,
			score: match.score,
			reason: match.reason,
			proceed: match.proceed,
			recipient: match.applyRecipient,
			subject: match.applySubject,
			required,
			missing: missing.map((kind) => ({ kind, label: DOC_LABELS[kind] ?? kind }))
		},
		job: {
			id: match.publicId,
			title: match.title ?? 'Untitled role',
			company: match.company ?? 'Employer',
			location: match.location,
			type: match.jobType,
			compensation: match.compensation,
			expires: match.expires,
			sourceUrl: match.sourceUrl
		},
		kit: kit
			? {
					id: kit.id,
					subject: kit.subject,
					recipient: kit.recipient,
					createdAt: kit.createdAt,
					merged: kit.metadata?.merged ?? false,
					blockers: kit.metadata?.blockers ?? [],
					autoSendReady: kit.metadata?.autoSendReady ?? false,
					notes: kit.metadata?.notes ?? null,
					attachments: kit.attachments.map((attachment, index) => ({
						index,
						name: attachment.name,
						mime: attachment.mime,
						bytes: decodedBase64Size(attachment.contentBase64)
					}))
				}
			: null,
		documents: documentRows.map((document) => ({
			id: document.id,
			type: document.type,
			createdAt: document.createdAt
		})),
		canForceApply:
			Boolean(profileRows[0]?.legacyUserId) &&
			profileRows[0]?.legacyUserId === envValue('APPLY_AGENT_LEGACY_USER_ID')
	};
};
