import { and, eq, gte, sql } from 'drizzle-orm';
import { getDb } from './db';
import { agentTasks, applicationKits } from './db/schema';

/** Never email the same recipient twice inside this window. */
export const RECIPIENT_COOLDOWN_DAYS = 7;

/** How long a re-posted version of the same vacancy is still considered a duplicate. */
const SAME_POSTING_WINDOW_DAYS = 45;

const CONTAINMENT_MIN_LENGTH = 12;
const CONTAINMENT_MIN_RATIO = 0.5;

export type DuplicateKind = 'recipient_cooldown' | 'same_posting';

export type DuplicateCheck = {
	blocked: boolean;
	kind: DuplicateKind | null;
	message: string | null;
	priorKitId: string | null;
	lastSentAt: Date | null;
};

const CLEAR: DuplicateCheck = {
	blocked: false,
	kind: null,
	message: null,
	priorKitId: null,
	lastSentAt: null
};

/**
 * Normalize a job title so the same vacancy posted on two sites compares equal.
 * "GRADUATE TRAINEE PROGRAMME 2027/2028 - 2 YEAR ON-THE-JOB TRAINING" becomes
 * "graduatetraineeprogramme202720282yearonthejobtraining".
 */
export function normalizeJobTitle(title: string | null | undefined): string {
	return (title ?? '')
		.normalize('NFKD')
		.replace(/[\u0300-\u036f]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '');
}

/**
 * True when one title is a meaningful prefix/substring of the other. Boards
 * routinely append "2 YEAR ON-THE-JOB TRAINING" or strip the year range, so an
 * exact string match is not enough to catch a re-post.
 */
export function isSamePostingTitle(a: string, b: string): boolean {
	if (!a || !b) return false;
	if (a === b) return true;
	const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
	if (shorter.length < CONTAINMENT_MIN_LENGTH) return false;
	return longer.includes(shorter) && shorter.length / longer.length >= CONTAINMENT_MIN_RATIO;
}

type PriorKit = {
	id: string;
	jobId: string | null;
	jobTitle: string | null;
	recipient: string;
	createdAt: Date;
};

/**
 * Block an application that would duplicate a recent one.
 *
 * Two independent guards mirror the behaviour of the old local orchestrator:
 *  - recipient cooldown: no second email to the same address within 7 days
 *  - same posting: the same vacancy re-scraped from another board
 *
 * A send only counts as delivered when the apply agent reported `sent: true`,
 * so a kit that was generated but never delivered does not lock the address.
 */
export async function checkPriorApplication(input: {
	userId: string;
	recipient: string;
	jobTitle: string;
	excludeJobPublicId?: string | null;
	excludeKitId?: string | null;
	cooldownDays?: number;
}): Promise<DuplicateCheck> {
	const recipient = input.recipient.trim().toLowerCase();
	if (!recipient) return CLEAR;

	const db = await getDb();
	const cooldownDays = input.cooldownDays ?? RECIPIENT_COOLDOWN_DAYS;
	const now = new Date();
	const cooldownCutoff = new Date(now.getTime() - cooldownDays * 24 * 60 * 60 * 1000);
	const postingCutoff = new Date(now.getTime() - SAME_POSTING_WINDOW_DAYS * 24 * 60 * 60 * 1000);

	const priorKits: PriorKit[] = await db
		.select({
			id: applicationKits.id,
			jobId: applicationKits.jobId,
			jobTitle: applicationKits.jobTitle,
			recipient: applicationKits.recipient,
			createdAt: applicationKits.createdAt
		})
		.from(applicationKits)
		.where(
			and(
				eq(applicationKits.userId, input.userId),
				sql`lower(${applicationKits.recipient}) = ${recipient}`,
				gte(applicationKits.createdAt, postingCutoff)
			)
		);

	const candidates = priorKits.filter(
		(kit) =>
			kit.id !== input.excludeKitId &&
			(!input.excludeJobPublicId || kit.jobId !== input.excludeJobPublicId)
	);
	if (candidates.length === 0) return CLEAR;

	const sends = await db
		.select({ result: agentTasks.result, completedAt: agentTasks.completedAt })
		.from(agentTasks)
		.where(
			and(
				eq(agentTasks.kind, 'apply'),
				eq(agentTasks.status, 'completed'),
				gte(agentTasks.completedAt, postingCutoff)
			)
		);

	// A queued-but-unsent application still counts: otherwise two different jobs
	// for the same recipient generated in the same run would both be sent.
	const inFlight = await db
		.select({ payload: agentTasks.payload })
		.from(agentTasks)
		.where(
			and(
				eq(agentTasks.kind, 'apply'),
				sql`${agentTasks.status} in ('pending', 'claimed')`
			)
		);
	const candidateIds = new Set(candidates.map((kit) => kit.id));
	for (const task of inFlight) {
		const kitId = task.payload?.kit_id;
		if (typeof kitId === 'string' && candidateIds.has(kitId)) {
			return {
				blocked: true,
				kind: 'recipient_cooldown',
				message: `An application to ${input.recipient} is already queued to send`,
				priorKitId: kitId,
				lastSentAt: null
			};
		}
	}

	const sentAtByKit = new Map<string, Date>();
	const sentRecipients: Date[] = [];
	for (const send of sends) {
		if (!send.completedAt) continue;
		const result = send.result ?? {};
		if (result.sent !== true) continue;
		if (typeof result.recipient === 'string') {
			if (result.recipient.trim().toLowerCase() === recipient) {
				sentRecipients.push(send.completedAt);
			}
		}
		if (typeof result.kit_id === 'string') {
			sentAtByKit.set(result.kit_id, send.completedAt);
		}
		if (typeof result.kitId === 'string') {
			sentAtByKit.set(result.kitId, send.completedAt);
		}
	}

	const lastSentAt = sentRecipients.sort((a, b) => b.getTime() - a.getTime())[0] ?? null;
	if (lastSentAt && lastSentAt >= cooldownCutoff) {
		const daysAgo = Math.floor((now.getTime() - lastSentAt.getTime()) / (24 * 60 * 60 * 1000));
		return {
			blocked: true,
			kind: 'recipient_cooldown',
			message: `Already applied to ${input.recipient} ${daysAgo === 0 ? 'today' : `${daysAgo} day(s) ago`} — ${cooldownDays}-day cooldown`,
			priorKitId: null,
			lastSentAt
		};
	}

	const titleKey = normalizeJobTitle(input.jobTitle);
	if (titleKey) {
		for (const kit of candidates) {
			if (
				isSamePostingTitle(titleKey, normalizeJobTitle(kit.jobTitle)) &&
				kit.createdAt >= postingCutoff
			) {
				return {
					blocked: true,
					kind: 'same_posting',
					message: `Same vacancy already applied for: "${kit.jobTitle}"`,
					priorKitId: kit.id,
					lastSentAt: sentAtByKit.get(kit.id) ?? null
				};
			}
		}
	}

	return CLEAR;
}
