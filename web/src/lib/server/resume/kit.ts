import { and, desc, eq } from 'drizzle-orm';
import { createAgentTask } from '../agent-tasks';
import { decodedBase64Size, MAX_ATTACHMENT_BYTES, safeFilename } from '../application-kit';
import { decryptSecret } from '../crypto';
import { getDb } from '../db';
import { checkPriorApplication } from '../dedup';
import { envValue } from '../env';
import {
	applicationKits,
	documents,
	jobMatches,
	jobs,
	oauthAccounts,
	userFiles,
	type ApplicationKitMetadata,
	type KitAttachment
} from '../db/schema';
import { getFile, putFile } from '../file-storage';
import { createGmailDraft, isGmailMock } from '../gmail';
import { renderApplication } from './render-service';
import type { ApplyDetails, CvTemplate } from './types';

export type KitJob = {
	matchId: string;
	jobId: number;
	publicId: string;
	title: string;
	company: string | null;
	description: string | null;
	applyInstructions: string | null;
	sourceUrl: string | null;
};

export type KitProfile = {
	name: string;
	email: string;
	headline: string | null;
	phone: string | null;
	cvTemplate: CvTemplate;
	legacyUserId: string | null;
};

export type UserFile = {
	id: string;
	filename: string;
	contentType: string;
	purpose: string;
	r2Key: string;
};

export type SupportingDocument = {
	kind: string;
	name: string;
	mime: string;
	contentBase64: string;
};

const DOC_LABELS: Record<string, string> = {
	cv: 'CV',
	cover_letter: 'cover letter',
	national_id: 'National ID',
	certificate: 'certificate or transcript',
	drivers_license: 'driver licence',
	document: 'supporting document'
};

export function bytesToBase64(bytes: Uint8Array): string {
	let binary = '';
	const chunk = 0x8000;
	for (let index = 0; index < bytes.length; index += chunk) {
		binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
	}
	return btoa(binary);
}

export function base64ToBytes(value: string): Uint8Array {
	const binary = atob(value);
	const bytes = new Uint8Array(binary.length);
	for (let index = 0; index < binary.length; index += 1) {
		bytes[index] = binary.charCodeAt(index);
	}
	return bytes;
}

export function normalizeDocument(value: string): string {
	const cleaned = value
		.toLowerCase()
		.replace(/[_-]+/g, ' ')
		.trim();
	if (cleaned.includes('cover')) return 'cover_letter';
	if (cleaned.includes('resume') || cleaned === 'cv' || cleaned.includes('curriculum')) {
		return 'cv';
	}
	if (
		cleaned.includes('national') ||
		cleaned.includes('passport') ||
		cleaned.includes('id doc') ||
		cleaned === 'id' ||
		cleaned.includes('identity')
	) {
		return 'national_id';
	}
	if (cleaned.includes('driver') || cleaned.includes('licence') || cleaned.includes('license')) {
		return 'drivers_license';
	}
	if (
		cleaned.includes('education') ||
		cleaned.includes('academic') ||
		cleaned.includes('certificate') ||
		cleaned.includes('certification') ||
		cleaned.includes('transcript')
	) {
		return 'certificate';
	}
	return 'document';
}

export function normalizeDocuments(
	values: string[] | undefined,
	coverLetter: string | null
): string[] {
	const found = new Set<string>();
	for (const value of values ?? []) found.add(normalizeDocument(value));
	found.add('cv');
	if (coverLetter) found.add('cover_letter');
	else found.delete('cover_letter');
	return [...found];
}

export function matchesFile(kind: string, file: UserFile): boolean {
	if (kind === 'national_id') {
		return (
			file.purpose === 'national_id' ||
			/national|passport|identification|\bid\b/i.test(file.filename)
		);
	}
	if (kind === 'certificate') {
		return (
			file.purpose === 'document' &&
			/certificat|transcript|degree|diploma|academic/i.test(file.filename)
		);
	}
	if (kind === 'drivers_license') {
		return /driver|licen[cs]e/i.test(file.filename);
	}
	return false;
}

export function mergeRequested(apply: ApplyDetails, emailText: string): boolean {
	if (apply.merged_pdf === true) return true;
	return /\b(single|one)\s+(pdf|file|document)\b|\bcombined\b|\bmerged?\b/i.test(emailText);
}

export async function loadSupportingDocuments(
	kinds: string[],
	files: UserFile[],
	blockers: string[]
): Promise<SupportingDocument[]> {
	const loaded: SupportingDocument[] = [];
	for (const kind of kinds) {
		if (kind === 'cv' || kind === 'cover_letter') continue;
		const file = files.find((candidate) => matchesFile(kind, candidate));
		if (!file) {
			const message = `Required document not uploaded: ${DOC_LABELS[kind] ?? kind}`;
			if (!blockers.includes(message)) blockers.push(message);
			continue;
		}
		const response = await getFile(file.r2Key);
		if (!response) {
			const message = `Could not load ${file.filename} from storage`;
			if (!blockers.includes(message)) blockers.push(message);
			continue;
		}
		const bytes = new Uint8Array(await response.arrayBuffer());
		loaded.push({
			kind,
			name: file.filename,
			mime: file.contentType,
			contentBase64: bytesToBase64(bytes)
		});
	}
	return loaded;
}

export async function loadUserFiles(userId: string): Promise<UserFile[]> {
	const db = await getDb();
	const rows = await db
		.select({
			id: userFiles.id,
			filename: userFiles.filename,
			contentType: userFiles.contentType,
			purpose: userFiles.purpose,
			r2Key: userFiles.r2Key
		})
		.from(userFiles)
		.where(eq(userFiles.userId, userId));
	return rows;
}

export type FinalizeInput = {
	userId: string;
	job: KitJob;
	profile: KitProfile;
	cv: unknown;
	coverLetter: string | null;
	applyDetails: ApplyDetails;
	requiredDocuments: string[];
	merge: boolean;
	recipient: string | null;
	subject: string;
	body: string;
	force?: boolean;
	dryRun?: boolean;
	queueSend?: boolean;
	replaceKitId?: string | null;
	notes?: string | null;
};

export type FinalizeResult = {
	kitId: string | null;
	blockers: string[];
	autoSendReady: boolean;
	cvPages: number;
	mergedPages: number | null;
	queuedSend: boolean;
	attachments: KitAttachment[];
};

export async function finalizeApplication(input: FinalizeInput): Promise<FinalizeResult> {
	const db = await getDb();
	const blockers: string[] = [];
	const availableFiles = await loadUserFiles(input.userId);
	const supporting = await loadSupportingDocuments(
		input.requiredDocuments,
		availableFiles,
		blockers
	);

	const merge = input.merge;
	const renderOutcome = await renderApplication({
		cv: input.cv,
		theme: input.profile.cvTemplate ?? 'harvard',
		coverLetter: input.coverLetter,
		attachments: supporting.map((document) => ({
			name: document.name,
			mime: document.mime,
			contentBase64: document.contentBase64
		})),
		merge
	});
	const rendered = renderOutcome.result;
	if (!rendered) {
		throw new Error(renderOutcome.error ?? 'Renderer unavailable');
	}

	const jobSlug = safeFilename(input.job.title);
	const nameSlug = safeFilename(input.profile.name);
	const cvName = `${nameSlug} CV - ${jobSlug}.pdf`;
	const coverName = `${nameSlug} Cover Letter - ${jobSlug}.pdf`;
	const coverDocxName = `${nameSlug} Cover Letter - ${jobSlug}.docx`;
	const mergedName = `${nameSlug} Application - ${jobSlug}.pdf`;
	const base = `users/${input.userId}/applications/${input.job.jobId}`;
	const cvKey = `${base}/${crypto.randomUUID()}-${cvName}`;
	const coverKey = `${base}/${crypto.randomUUID()}-${coverName}`;
	const mergedKey = rendered.mergedPdf
		? `${base}/${crypto.randomUUID()}-${mergedName}`
		: null;

	const cvBytes = base64ToBytes(rendered.cvPdf);
	if (!(await putFile(cvKey, new File([cvBytes as BlobPart], cvName, { type: 'application/pdf' })))) {
		throw new Error('Could not store the CV PDF');
	}
	if (
		rendered.coverLetterPdf &&
		!(await putFile(
			coverKey,
			new File([base64ToBytes(rendered.coverLetterPdf) as BlobPart], coverName, {
				type: 'application/pdf'
			})
		))
	) {
		throw new Error('Could not store the cover letter PDF');
	}
	if (
		mergedKey &&
		rendered.mergedPdf &&
		!(await putFile(
			mergedKey,
			new File([base64ToBytes(rendered.mergedPdf) as BlobPart], mergedName, {
				type: 'application/pdf'
			})
		))
	) {
		throw new Error('Could not store the merged PDF');
	}

	if (input.replaceKitId) {
		await db.delete(documents).where(
			and(eq(documents.userId, input.userId), eq(documents.jobId, input.job.jobId))
		);
		await db.delete(applicationKits).where(eq(applicationKits.id, input.replaceKitId));
	}

	const cvDocumentId = crypto.randomUUID();
	await db.insert(documents).values({
		id: cvDocumentId,
		userId: input.userId,
		jobId: input.job.jobId,
		documentType: 'resume',
		content: JSON.stringify(input.cv),
		rendercvYaml: JSON.stringify({
			cv: input.cv,
			design: { theme: input.profile.cvTemplate ?? 'harvard' }
		}),
		pdfPath: cvKey,
		promptName: 'ats_and_cover_v1',
		model: 'rendercv'
	});

	if (input.coverLetter && rendered.coverLetterPdf) {
		await db.insert(documents).values({
			id: crypto.randomUUID(),
			userId: input.userId,
			jobId: input.job.jobId,
			documentType: 'cover_letter',
			content: input.coverLetter,
			pdfPath: coverKey,
			promptName: 'ats_and_cover_v1',
			model: 'rendercv'
		});
	}

	const attachments: KitAttachment[] = [];
	if (rendered.mergedPdf) {
		attachments.push({
			name: mergedName,
			mime: 'application/pdf',
			contentBase64: rendered.mergedPdf
		});
	} else {
		attachments.push({ name: cvName, mime: 'application/pdf', contentBase64: rendered.cvPdf });
		if (rendered.coverLetterDocx) {
			attachments.push({
				name: coverDocxName,
				mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
				contentBase64: rendered.coverLetterDocx
			});
		} else if (rendered.coverLetterPdf) {
			attachments.push({
				name: coverName,
				mime: 'application/pdf',
				contentBase64: rendered.coverLetterPdf
			});
		}
		for (const document of supporting) {
			attachments.push({
				name: document.name,
				mime: document.mime,
				contentBase64: document.contentBase64
			});
		}
	}

	const attachmentBytes = attachments.reduce(
		(sum, attachment) => sum + decodedBase64Size(attachment.contentBase64),
		0
	);
	if (attachmentBytes > MAX_ATTACHMENT_BYTES) {
		blockers.push(`Attachments exceed ${Math.round(MAX_ATTACHMENT_BYTES / (1024 * 1024))} MB`);
	}

	const autoSendReady = blockers.length === 0;
	const metadata: ApplicationKitMetadata = {
		selectedField: null,
		subjectTemplate: input.applyDetails.subject ?? null,
		recipients: input.recipient ? [{ email: input.recipient, field: null }] : [],
		requiredDocuments: input.requiredDocuments,
		combineAttachments: merge,
		blockers,
		confidence: 0.9,
		autoSendReady,
		merged: Boolean(rendered.mergedPdf),
		notes: input.notes ?? null,
		forced: input.force === true
	};

	if (input.recipient && input.force !== true) {
		const duplicate = await checkPriorApplication({
			userId: input.userId,
			recipient: input.recipient,
			jobTitle: input.job.title,
			excludeJobPublicId: input.job.publicId,
			excludeKitId: input.replaceKitId ?? null
		});

		if (duplicate.blocked) {
			blockers.push(duplicate.message ?? 'Duplicate application');
			await db
				.update(jobMatches)
				.set({
					status: 'duplicate',
					applyAction: 'email',
					applyRecipient: input.recipient,
					applySubject: input.subject,
					applyBody: input.body,
					proceed: 'duplicate_skipped'
				})
				.where(eq(jobMatches.id, input.job.matchId));

			return {
				kitId: null,
				blockers,
				autoSendReady: false,
				cvPages: rendered.cvPages,
				mergedPages: rendered.mergedPages,
				queuedSend: false,
				attachments
			};
		}
	}

	let kitId: string | null = null;
	if (input.recipient) {
		kitId = crypto.randomUUID();
		await db.insert(applicationKits).values({
			id: kitId,
			userId: input.userId,
			jobId: input.job.publicId,
			jobTitle: input.job.title,
			company: input.job.company,
			recipient: input.recipient,
			subject: input.subject,
			body: input.body,
			attachments,
			metadata
		});

		const gmail = await db
			.select()
			.from(oauthAccounts)
			.where(and(eq(oauthAccounts.userId, input.userId), eq(oauthAccounts.provider, 'gmail')))
			.limit(1);
		if (gmail[0] && !isGmailMock()) {
			try {
				const refreshToken = await decryptSecret(
					gmail[0].encryptedRefreshToken,
					gmail[0].iv
				);
				await createGmailDraft({
					refreshToken,
					to: input.recipient,
					subject: input.subject,
					body: input.body,
					attachments
				});
			} catch {
				// Draft creation is best-effort; the kit is still downloadable.
			}
		}
	}

	await db
		.update(jobMatches)
		.set({
			status: 'generated',
			applyAction: input.recipient ? 'email' : 'external_link',
			applyRecipient: input.recipient,
			applySubject: input.subject,
			applyBody: input.body,
			applyUrl: input.recipient
				? null
				: input.applyDetails.action === 'external_link'
					? (input.applyDetails.url ?? input.job.sourceUrl ?? null)
					: null,
			requiredDocs: JSON.stringify(input.requiredDocuments),
			proceed: blockers.length === 0 ? 'apply_now' : 'needs_docs'
		})
		.where(eq(jobMatches.id, input.job.matchId));

	let queuedSend = false;
	const ownerLegacyUserId = envValue('APPLY_AGENT_LEGACY_USER_ID');
	if (
		input.queueSend === true &&
		!input.dryRun &&
		kitId &&
		input.recipient &&
		(input.force === true || blockers.length === 0) &&
		input.profile.legacyUserId &&
		ownerLegacyUserId === input.profile.legacyUserId
	) {
		try {
			await createAgentTask('apply', {
				legacy_user_id: input.profile.legacyUserId,
				web_user_id: input.userId,
				match_id: input.job.matchId,
				kit_id: kitId,
				limit: 1
			});
			queuedSend = true;
		} catch (error) {
			console.error('Could not queue the apply task', error);
		}
	}

	return {
		kitId,
		blockers,
		autoSendReady,
		cvPages: rendered.cvPages,
		mergedPages: rendered.mergedPages,
		queuedSend,
		attachments
	};
}

export async function loadKitContext(matchId: string, userId: string) {
	const db = await getDb();
	const rows = await db
		.select({
			matchId: jobMatches.id,
			jobId: jobs.id,
			publicId: jobs.publicId,
			title: jobs.title,
			company: jobs.company,
			description: jobs.description,
			applyInstructions: jobs.applyInstructions,
			sourceUrl: jobs.sourceUrl,
			status: jobMatches.status,
			requiredDocs: jobMatches.requiredDocs,
			applyRecipient: jobMatches.applyRecipient,
			applySubject: jobMatches.applySubject,
			applyBody: jobMatches.applyBody
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(and(eq(jobMatches.id, matchId), eq(jobMatches.userId, userId)))
		.limit(1);
	const job = rows[0];
	if (!job) return null;

	const kitRows = await db
		.select()
		.from(applicationKits)
		.where(
			and(
				eq(applicationKits.userId, userId),
				eq(applicationKits.jobId, job.publicId)
			)
		)
		.orderBy(desc(applicationKits.createdAt))
		.limit(1);

	const documentRows = await db
		.select()
		.from(documents)
		.where(and(eq(documents.userId, userId), eq(documents.jobId, job.jobId)));

	return { job, kit: kitRows[0] ?? null, documents: documentRows };
}
