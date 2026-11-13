import { and, desc, eq } from 'drizzle-orm';
import { getDb } from '../db';
import {
	applicationKits,
	documents,
	jobMatches,
	jobs,
	profiles,
	user as userTable
} from '../db/schema';
import { fallbackLetter } from '../generation';
import { chooseRecipient, emailsFrom } from './recipients';
import {
	finalizeApplication,
	loadUserFiles,
	matchesFile,
	mergeRequested,
	normalizeDocuments,
	type KitJob,
	type KitProfile
} from './kit';
import type { CvTemplate } from './types';

export type RebuildOptions = {
	force?: boolean;
	queueSend?: boolean;
	cvOverride?: unknown;
	coverLetterOverride?: string | null;
};

export type RebuildResult = {
	ok: boolean;
	status?: string;
	kitId?: string | null;
	blockers?: string[];
	autoSendReady?: boolean;
	queuedSend?: boolean;
	error?: string;
};

export function cvToRenderData(
	documentContent: string | null | undefined
): unknown | null {
	if (!documentContent) return null;
	try {
		const parsed = JSON.parse(documentContent) as { cv?: unknown };
		return parsed.cv ?? parsed;
	} catch {
		return null;
	}
}

/**
 * Re-runs the render + validation step for an existing match.
 *
 * Used by three user actions:
 *  - revalidate: user uploaded a missing document or completed their profile
 *  - force: user explicitly accepts the blockers (owner-only today)
 *  - edit: user changed the CV or cover letter in the browser
 */
export async function rebuildApplication(
	matchId: string,
	userId: string,
	options: RebuildOptions = {}
): Promise<RebuildResult> {
	const db = await getDb();
	const rows = await db
		.select({
			matchId: jobMatches.id,
			status: jobMatches.status,
			requiredDocs: jobMatches.requiredDocs,
			applySubject: jobMatches.applySubject,
			applyBody: jobMatches.applyBody,
			applyRecipient: jobMatches.applyRecipient,
			jobId: jobs.id,
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			description: jobs.description,
			applyInstructions: jobs.applyInstructions,
			sourceUrl: jobs.sourceUrl
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(and(eq(jobMatches.id, matchId), eq(jobMatches.userId, userId)))
		.limit(1);

	const match = rows[0];
	if (!match) return { ok: false, error: 'Match not found' };

	const profileRows = await db
		.select({
			name: userTable.name,
			email: userTable.email,
			headline: profiles.headline,
			phone: profiles.phone,
			cvTemplate: profiles.cvTemplate,
			legacyUserId: profiles.legacyUserId,
			resumeText: profiles.resumeText
		})
		.from(profiles)
		.innerJoin(userTable, eq(profiles.userId, userTable.id))
		.where(eq(profiles.userId, userId))
		.limit(1);

	const profile = profileRows[0];
	if (!profile) return { ok: false, error: 'Profile not found' };

	const documentRows = await db
		.select()
		.from(documents)
		.where(and(eq(documents.userId, userId), eq(documents.jobId, match.jobId)))
		.orderBy(desc(documents.createdAt));

	const cvDocument = documentRows.find((row) => row.documentType === 'resume');
	const coverDocument = documentRows.find((row) => row.documentType === 'cover_letter');

	const cv = options.cvOverride ?? cvToRenderData(cvDocument?.content ?? null);
	if (!cv) return { ok: false, error: 'No generated CV to rebuild from' };

	const coverLetter =
		options.coverLetterOverride !== undefined
			? options.coverLetterOverride
			: (coverDocument?.content ?? null);

	if (coverLetter === null && coverDocument?.content === null) {
		return { ok: false, error: 'This application has no cover letter text to rebuild' };
	}

	const kitRows = await db
		.select()
		.from(applicationKits)
		.where(
			and(
				eq(applicationKits.userId, userId),
				eq(applicationKits.jobId, match.publicId)
			)
		)
		.orderBy(desc(applicationKits.createdAt))
		.limit(1);
	const existingKit = kitRows[0] ?? null;

	const emailText = `${match.applyInstructions ?? ''}\n${match.description ?? ''}`;
	const candidates = emailsFrom(emailText);
	const recipient =
		existingKit?.recipient ??
		match.applyRecipient ??
		chooseRecipient(candidates, `${profile.headline ?? ''} ${profile.name} ${match.title}`);

	const requiredDocuments = normalizeDocuments(
		match.requiredDocs ? (JSON.parse(match.requiredDocs) as string[]) : [],
		coverLetter
	);

	const title = match.title ?? 'Untitled role';
	const kitJob: KitJob = {
		matchId: match.matchId,
		jobId: match.jobId,
		publicId: match.publicId,
		title,
		company: match.company,
		description: match.description,
		applyInstructions: match.applyInstructions,
		sourceUrl: match.sourceUrl
	};
	const kitProfile: KitProfile = {
		name: profile.name,
		email: profile.email,
		headline: profile.headline,
		phone: profile.phone,
		cvTemplate: (profile.cvTemplate ?? 'harvard') as CvTemplate,
		legacyUserId: profile.legacyUserId
	};
	const subject = existingKit?.subject ?? match.applySubject ?? `Application: ${title}`;
	const body =
		existingKit?.body ??
		match.applyBody ??
		fallbackLetter(profile.name, title, match.company ?? '', profile.resumeText ?? '');

	try {
		const result = await finalizeApplication({
			userId,
			job: kitJob,
			profile: kitProfile,
			cv,
			coverLetter,
			applyDetails: { subject },
			requiredDocuments,
			merge: mergeRequested({ subject }, emailText),
			recipient,
			subject,
			body,
			force: options.force === true,
			queueSend: options.queueSend === true,
			replaceKitId: existingKit?.id ?? null,
			notes: existingKit?.metadata?.notes ?? null
		});

		return {
			ok: true,
			status: result.blockers.length === 0 ? 'ready' : 'needs_review',
			kitId: result.kitId,
			blockers: result.blockers,
			autoSendReady: result.autoSendReady,
			queuedSend: result.queuedSend
		};
	} catch (error) {
		return {
			ok: false,
			error: error instanceof Error ? error.message : 'Rebuild failed'
		};
	}
}

export async function missingDocuments(userId: string, required: string[]): Promise<string[]> {
	const files = await loadUserFiles(userId);
	const missing: string[] = [];
	for (const kind of required) {
		if (kind === 'cv' || kind === 'cover_letter') continue;
		if (!files.some((file) => matchesFile(kind, file))) missing.push(kind);
	}
	return missing;
}
