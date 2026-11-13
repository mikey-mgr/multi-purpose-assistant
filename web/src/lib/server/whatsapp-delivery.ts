import { and, desc, eq, or } from 'drizzle-orm';
import { getDb } from './db';
import { applicationKits, jobMatches, jobs, whatsappPilot } from './db/schema';
import { sendWhatsappDocument, sendWhatsappText } from './whatsapp';

/**
 * Deliver a generated CV / cover letter to a user over WhatsApp.
 *
 * Shared by two flows so behaviour is identical whether the kit was just
 * generated from a WhatsApp JD or requested later by message.
 */

export type DeliverableFile = {
	base64: string;
	filename: string;
	mimetype: string;
	label: string;
};

type KitAttachments = Array<{ name: string; mime: string; contentBase64: string }>;

/** Normalise "263771234567@s.whatsapp.net" and "0771234567" to 2637... */
export function normalizePhoneForLookup(value: string): string {
	const digits = value.split('@')[0].replace(/[^0-9]/g, '');
	return digits.startsWith('0') ? `263${digits.slice(1)}` : digits;
}

/** Resolve a phone number to the pilot user who owns it, or null. */
export async function userIdForPhone(phone: string): Promise<string | null> {
	const db = await getDb();
	const rows = await db
		.select({ userId: whatsappPilot.userId, phone: whatsappPilot.phone })
		.from(whatsappPilot)
		.where(eq(whatsappPilot.status, 'active'));

	const wanted = normalizePhoneForLookup(phone);
	return rows.find((row) => normalizePhoneForLookup(row.phone) === wanted)?.userId ?? null;
}

export type DeliveryKit = {
	kitId: string;
	jobTitle: string;
	company: string | null;
	attachments: KitAttachments;
};

/**
 * Find the kit to deliver.
 *
 * With a reference we match on job title or company; without one we fall back to
 * the most recent kit, which is what "send me my CV" usually means.
 */
export async function findKitForDelivery(input: {
	userId: string;
	reference?: string | null;
}): Promise<DeliveryKit | null> {
	const db = await getDb();
	const rows = await db
		.select({
			kitId: applicationKits.id,
			jobTitle: applicationKits.jobTitle,
			company: applicationKits.company,
			attachments: applicationKits.attachments,
			createdAt: applicationKits.createdAt
		})
		.from(applicationKits)
		.where(eq(applicationKits.userId, input.userId))
		.orderBy(desc(applicationKits.createdAt))
		.limit(25);

	if (rows.length === 0) return null;

	const reference = input.reference?.trim().toLowerCase();
	if (reference) {
		const found = rows.find(
			(row) =>
				(row.jobTitle ?? '').toLowerCase().includes(reference) ||
				(row.company ?? '').toLowerCase().includes(reference)
		);
		// A reference that matches nothing is not silently replaced by the
		// newest kit: the user asked for a specific job.
		return found ?? null;
	}

	return rows[0];
}

/**
 * Choose the files to send.
 *
 * Kits store the CV as PDF and the cover letter as DOCX when the render service
 * returns one, so both extensions are deliverable. A kit whose only file is the
 * merged "Application" PDF is sent as-is rather than sending nothing.
 */
export function filesFromAttachments(attachments: KitAttachments): DeliverableFile[] {
	const files: DeliverableFile[] = [];
	const merged: DeliverableFile[] = [];

	for (const attachment of attachments) {
		const lower = attachment.name.toLowerCase();
		const file: DeliverableFile = {
			base64: attachment.contentBase64,
			filename: attachment.name,
			mimetype: attachment.mime,
			label: lower.includes('cover')
				? 'Cover letter'
				: lower.includes('application')
					? 'Application'
					: 'CV'
		};

		if (lower.includes('application') && lower.endsWith('.pdf')) {
			merged.push(file);
			continue;
		}
		files.push(file);
	}

	// Separate files already contain everything; the merged copy would duplicate.
	return files.length > 0 ? files : merged;
}

/** Send a kit's documents to a phone. */
export async function deliverKitToWhatsapp(input: {
	phone: string;
	kit: Pick<DeliveryKit, 'jobTitle' | 'company' | 'attachments'>;
}): Promise<{ sent: number; files: number }> {
	const files = filesFromAttachments(input.kit.attachments);
	if (files.length === 0) return { sent: 0, files: 0 };

	const where = input.kit.company
		? `${input.kit.jobTitle} at ${input.kit.company}`
		: input.kit.jobTitle;

	let sent = 0;
	for (const file of files) {
		const ok = await sendWhatsappDocument({
			phone: input.phone,
			base64: file.base64,
			filename: file.filename,
			mimetype: file.mimetype,
			caption: `${file.label} - ${where}`
		});
		if (ok) sent += 1;
	}
	return { sent, files: files.length };
}

/** Tell the user we could not find what they asked for. */
export async function replyMissingKit(phone: string, available: string[]): Promise<void> {
	const tail = available.length
		? `\n\nYour latest generated CVs:\n${available.map((title) => `- ${title}`).join('\n')}`
		: '';
	await sendWhatsappText(
		phone,
		`I could not find a generated CV for that. Send the job title exactly as it appears, or generate one from your dashboard first.${tail}`
	);
}

/** Recent job titles the user has generated documents for. */
export async function recentJobTitles(userId: string, limit = 5): Promise<string[]> {
	const db = await getDb();
	const rows = await db
		.select({ title: jobs.title })
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.userId, userId),
				or(eq(jobMatches.status, 'generated'), eq(jobMatches.status, 'applied'))
			)
		)
		.orderBy(desc(jobMatches.createdAt))
		.limit(limit);
	return rows.map((row) => row.title ?? '').filter(Boolean);
}

/**
 * Jobs this user submitted themselves and which were matched, even if the
 * matcher rejected them.
 *
 * A user who forwards a vacancy has already decided they want it; refusing to
 * produce documents because the scoring gate disagrees would make WhatsApp feel
 * broken. Only their own submissions qualify - never scraped jobs.
 */
export async function ownRejectedJob(
	userId: string,
	reference: string
): Promise<{ matchId: string; jobId: number; title: string; company: string | null } | null> {
	const db = await getDb();
	const wanted = reference.trim().toLowerCase();
	if (wanted.length < 3) return null;

	const rows = await db
		.select({
			matchId: jobMatches.id,
			jobId: jobs.id,
			title: jobs.title,
			company: jobs.company
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.userId, userId),
				eq(jobs.ownerUserId, userId),
				or(eq(jobMatches.status, 'rejected'), eq(jobMatches.status, 'matched'))
			)
		)
		.orderBy(desc(jobMatches.createdAt))
		.limit(25);

	const match = rows.find(
		(row) =>
			(row.title ?? '').toLowerCase().includes(wanted) ||
			(row.company ?? '').toLowerCase().includes(wanted)
	);
	if (!match) return null;
	return {
		matchId: match.matchId,
		jobId: match.jobId,
		title: match.title ?? '',
		company: match.company ?? null
	};
}
