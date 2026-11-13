import { and, desc, eq, inArray, isNull, or, sql } from 'drizzle-orm';
import { getDb } from './db';
import { jobMatches, jobs, profiles, user as userTable } from './db/schema';
import { buildCvData } from './resume/build-cv';
import { normalizeCoverLetter } from './resume/cover-letter';
import { extractResumeProfile } from './resume/extract';
import {
	finalizeApplication,
	loadUserFiles,
	matchesFile,
	mergeRequested,
	normalizeDocuments,
	type KitJob,
	type KitProfile
} from './resume/kit';
import { chooseRecipient, emailsFrom } from './resume/recipients';
import { tailorApplication } from './resume/tailor';
import type { ApplyDetails, CvTemplate, ResumeProfile } from './resume/types';

export function fallbackLetter(
	name: string,
	jobTitle: string,
	company: string,
	resumeText: string
): string {
	const snippet = resumeText
		.replace(/\s+/g, ' ')
		.trim()
		.split(/(?<=[.!?])\s+/)
		.slice(0, 3)
		.join(' ');
	return `Dear Hiring Manager,\n\nI am applying for the ${jobTitle} role${company ? ` at ${company}` : ''}. ${snippet}\n\nI would welcome the opportunity to discuss how my experience can contribute to your team.\n\nRegards,\n${name}`;
}

export function validRecipient(
	apply: ApplyDetails,
	emailText: string,
	context: string,
	blockers: string[]
): string | null {
	const candidates = emailsFrom(emailText);
	const proposed = apply.recipient?.trim().toLowerCase() ?? null;
	if (proposed && candidates.includes(proposed)) return proposed;
	if (proposed && candidates.length === 0) return proposed;
	const fallback = chooseRecipient(candidates, context);
	if (proposed && !candidates.includes(proposed)) {
		blockers.push('The selected recipient was not present in the job instructions');
	}
	if (!fallback && candidates.length > 1) {
		blockers.push('Multiple application addresses; no confident recipient match');
	}
	if (!fallback && candidates.length === 0) {
		blockers.push('No application email found');
	}
	return fallback;
}

export async function getOrExtractProfile(input: {
	userId: string;
	name: string;
	email: string;
	resumeText: string | null;
	resumeData: ResumeProfile | null;
	phone: string | null;
	linkedinUrl: string | null;
}): Promise<ResumeProfile | null> {
	if (input.resumeData) return input.resumeData;
	if (!input.resumeText) return null;
	const extracted = await extractResumeProfile({
		name: input.name,
		email: input.email,
		resumeText: input.resumeText
	});
	if (!extracted) return null;
	extracted.user.email = extracted.user.email || input.email;
	extracted.user.phone_1 = extracted.user.phone_1 || input.phone;
	extracted.user.linkedin_url = extracted.user.linkedin_url || input.linkedinUrl;

	const db = await getDb();
	await db
		.update(profiles)
		.set({
			resumeData: extracted,
			phone: extracted.user.phone_1 ?? input.phone,
			linkedinUrl: extracted.user.linkedin_url ?? input.linkedinUrl,
			updatedAt: new Date()
		})
		.where(eq(profiles.userId, input.userId));
	return extracted;
}

export async function generateForMatchedJob(
	userId: string,
	options: {
		dryRun?: boolean;
		allowSend?: boolean;
		jobIds?: number[];
		/**
		 * Generate even though the match was rejected. Only used when the user
		 * asks for a job they submitted themselves, so a scoring gate never
		 * blocks a document they explicitly requested.
		 */
		force?: boolean;
	} = {}
): Promise<{
	generated: boolean;
	jobId?: number;
	recipient?: string | null;
	draft?: boolean;
	autoSendReady?: boolean;
	blockers?: string[];
	selectedField?: string | null;
	theme?: CvTemplate;
	cvPages?: number;
	mergedPages?: number | null;
	error?: string;
}> {
	const db = await getDb();
	const rows = await db
		.select({
			matchId: jobMatches.id,
			jobId: jobs.id,
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			location: jobs.location,
			description: jobs.description,
			applyInstructions: jobs.applyInstructions,
			sourceUrl: jobs.sourceUrl,
			jobType: jobs.jobType
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.userId, userId),
				options.force
					? inArray(jobMatches.status, ['matched', 'rejected'])
					: eq(jobMatches.status, 'matched'),
				or(isNull(jobs.expires), sql`${jobs.expires} >= current_date`),
				options.jobIds?.length ? inArray(jobMatches.jobId, options.jobIds) : undefined
			)
		)
		.orderBy(desc(jobMatches.score), desc(jobMatches.createdAt))
		.limit(1);

	const job = rows[0];
	if (!job) return { generated: false };

	const profileRows = await db
		.select({
			name: userTable.name,
			email: userTable.email,
			headline: profiles.headline,
			location: profiles.location,
			resumeText: profiles.resumeText,
			resumeData: profiles.resumeData,
			phone: profiles.phone,
			linkedinUrl: profiles.linkedinUrl,
			cvTemplate: profiles.cvTemplate,
			references: profiles.references,
			referencesEnabled: profiles.referencesEnabled,
			legacyUserId: profiles.legacyUserId
		})
		.from(profiles)
		.innerJoin(userTable, eq(profiles.userId, userTable.id))
		.where(eq(profiles.userId, userId))
		.limit(1);

	const profile = profileRows[0];
	if (!profile) return { generated: false, error: 'Profile not found' };
	if (!job.title) return { generated: false, error: 'Job title is missing' };

	const resumeData = await getOrExtractProfile({
		userId,
		name: profile.name,
		email: profile.email,
		resumeText: profile.resumeText,
		resumeData: profile.resumeData,
		phone: profile.phone,
		linkedinUrl: profile.linkedinUrl
	});
	if (!resumeData) {
		return { generated: false, error: 'No structured resume data or resume text' };
	}

	const availableFiles = await loadUserFiles(userId);
	const documentLabels: Record<string, string> = {
		resume: 'CV is generated automatically',
		cover_letter: 'Cover letter is generated automatically'
	};
	if (availableFiles.some((file) => matchesFile('national_id', file))) {
		documentLabels.id_doc = 'National ID on file';
	}
	if (availableFiles.some((file) => matchesFile('drivers_license', file))) {
		documentLabels.drivers_license = 'Driver licence on file';
	}
	if (availableFiles.some((file) => matchesFile('certificate', file))) {
		documentLabels.education_cert = 'Academic certificate on file';
	}

	const tailored = await tailorApplication(resumeData, {
		title: job.title,
		company: job.company,
		description: job.description ?? '',
		location: job.location,
		jobType: job.jobType,
		applyInstructions: job.applyInstructions,
		documents: documentLabels
	});
	if (!tailored) {
		return { generated: false, error: 'Tailoring failed' };
	}

	const candidateName =
		`${resumeData.user.first_name ?? ''} ${resumeData.user.last_name ?? ''}`.trim() ||
		profile.name;
	const contact = {
		name: candidateName,
		email: resumeData.user.email || profile.email,
		phone: resumeData.user.phone_1 || resumeData.user.phone_2 || profile.phone
	};
	const coverLetter = tailored.coverLetter
		? normalizeCoverLetter(tailored.coverLetter, contact)
		: null;
	const cv = buildCvData(resumeData, tailored.resume, {
		references: profile.references ?? [],
		referencesEnabled: profile.referencesEnabled ?? false
	});
	const emailText = `${job.applyInstructions ?? ''}\n${job.description ?? ''}`;
	const blockers: string[] =
		tailored.applyDetails.proceed === 'needs_info'
			? ['Tailoring reported missing core information']
			: [];

	const recipient = validRecipient(
		tailored.applyDetails,
		emailText,
		`${profile.headline ?? ''} ${candidateName} ${job.title}`,
		blockers
	);
	const requiredDocuments = normalizeDocuments(tailored.applyDetails.required_docs, coverLetter);
	const subject = tailored.applyDetails.subject?.trim() || `Application: ${job.title}`;
	const body =
		tailored.applyDetails.body?.trim() ||
		fallbackLetter(candidateName, job.title, job.company ?? '', profile.resumeText ?? '');

	const kitJob: KitJob = {
		matchId: job.matchId,
		jobId: job.jobId,
		publicId: job.publicId,
		title: job.title,
		company: job.company,
		description: job.description,
		applyInstructions: job.applyInstructions,
		sourceUrl: job.sourceUrl
	};
	const kitProfile: KitProfile = {
		name: candidateName,
		email: profile.email,
		headline: profile.headline,
		phone: profile.phone,
		cvTemplate: profile.cvTemplate,
		legacyUserId: profile.legacyUserId
	};

	try {
		const result = await finalizeApplication({
			userId,
			job: kitJob,
			profile: kitProfile,
			cv,
			coverLetter,
			applyDetails: tailored.applyDetails,
			requiredDocuments,
			merge: mergeRequested(tailored.applyDetails, emailText),
			recipient,
			subject,
			body,
			dryRun: options.dryRun,
			queueSend: options.allowSend === true,
			notes: tailored.missingResources
		});

		const merged = [...blockers, ...result.blockers.filter((b) => !blockers.includes(b))];
		return {
			generated: true,
			jobId: job.jobId,
			recipient,
			draft: false,
			autoSendReady: result.autoSendReady && merged.length === 0,
			blockers: merged,
			selectedField: null,
			theme: profile.cvTemplate ?? 'harvard',
			cvPages: result.cvPages,
			mergedPages: result.mergedPages
		};
	} catch (error) {
		return {
			generated: false,
			error: error instanceof Error ? error.message : 'Generation failed'
		};
	}
}
