import { json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { upsertAgentJobs } from '../../../../lib/server/agent-tasks';
import { timingSafeEqual } from '../../../../lib/server/crypto';
import { getDb } from '../../../../lib/server/db';
import { profiles, jobs, jobMatches, whatsappPilot } from '../../../../lib/server/db/schema';
import { envValue } from '../../../../lib/server/env';
import { generateForMatchedJob } from '../../../../lib/server/generation';
import { triggerMatchingForUser } from '../../../../lib/server/matching';
import {
	deliverKitToWhatsapp,
	findKitForDelivery,
	ownRejectedJob,
	recentJobTitles,
	replyMissingKit
} from '../../../../lib/server/whatsapp-delivery';
import { detectDocumentRequest, parseImageJob, parseTextJob } from '../../../../lib/server/whatsapp-parse';

const input = z
	.object({
		text: z.string().min(1).max(20_000).optional(),
		image_base64: z.string().min(1).max(15_000_000).optional(),
		mimetype: z.string().max(100).optional(),
		/** Sender as WhatsApp JID ("263771234567@s.whatsapp.net") or bare digits. */
		sender: z.string().max(120).optional(),
		/** Explicit user id, used by the owner's own tooling. */
		user_id: z.string().min(1).max(100).optional()
	})
	.strict();

const MIMETYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);

function authorized(request: Request): boolean {
	const expected = envValue('WHATSAPP_WEBHOOK_SECRET');
	const supplied = request.headers.get('x-webhook-secret');
	if (!expected || !supplied) return false;
	return timingSafeEqual(expected, supplied);
}

/** Reduce "263771234567@s.whatsapp.net" and "0771234567" to a comparable form. */
function normalizePhone(value: string): string {
	const digits = value.split('@')[0].replace(/[^0-9]/g, '');
	// Zimbabwean local numbers start 07..., international as 2637...
	if (digits.startsWith('0')) return `263${digits.slice(1)}`;
	return digits;
}

/**
 * Ingest a WhatsApp message as a job posting.
 *
 * The sender is resolved to their own account; documents are never generated
 * from another user's profile. If the sender is not a registered pilot user we
 * refuse rather than guessing, because a wrong profile would mean tailoring and
 * auto-sending someone else's CV.
 */
export const POST: RequestHandler = async (event) => {
	if (!authorized(event.request)) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = input.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid payload', issues: parsed.error.flatten() }, { status: 400 });
	}

	const { text, image_base64, mimetype } = parsed.data;
	if (!text && !image_base64) {
		return json({ error: 'Provide text or image_base64' }, { status: 400 });
	}

	const db = await getDb();

	// Resolve who sent this BEFORE parsing, so an unregistered number costs
	// nothing and can never borrow another user's profile. An explicit user_id
	// wins (owner tooling); otherwise the sender's phone must match an active
	// pilot signup. There is deliberately no "any profile" fallback: generating
	// from the wrong profile would tailor and auto-send another user's CV.
	let resolvedUserId: string | null = parsed.data.user_id ?? null;

	if (!resolvedUserId) {
		const sender = parsed.data.sender;
		if (!sender) {
			return json(
				{ ok: false, error: 'sender is required to identify the user' },
				{ status: 400 }
			);
		}

		const wanted = normalizePhone(sender);
		const pilots = await db
			.select({ phone: whatsappPilot.phone, userId: whatsappPilot.userId })
			.from(whatsappPilot)
			.where(eq(whatsappPilot.status, 'active'));

		const match = pilots.find((row) => normalizePhone(row.phone) === wanted);
		if (!match) {
			return json(
				{ ok: false, parsed: null, error: 'sender_not_registered', sender: wanted },
				{ status: 200 }
			);
		}
		resolvedUserId = match.userId;
	}

	const profileRows = await db
		.select({ userId: profiles.userId, legacyUserId: profiles.legacyUserId })
		.from(profiles)
		.where(eq(profiles.userId, resolvedUserId))
		.limit(1);

	const profile = profileRows[0];
	if (!profile) {
		return json({ ok: false, parsed: null, error: 'profile_not_found' }, { status: 200 });
	}

	// A user asking for documents they already have must not be treated as a JD.
	// This runs before parsing so "send me my CV for NetOne" never becomes a job.
	if (text) {
		const request = detectDocumentRequest(text);
		if (request.wantsCopy) {
			const phone = parsed.data.sender;
			if (!phone) {
				return json({ ok: false, error: 'sender required' }, { status: 400 });
			}

			const kit = await findKitForDelivery({
				userId: profile.userId,
				reference: request.reference
			});

			if (!kit && request.reference) {
				// Nothing generated yet. If this is a job the user submitted
				// themselves, generate on demand - they clearly want it, even if
				// the scoring gate rejected it.
				const own = await ownRejectedJob(profile.userId, request.reference);
				if (own) {
					await generateForMatchedJob(profile.userId, {
						jobIds: [own.jobId],
						allowSend: false,
						force: true
					}).catch((error) => console.error('Force generation failed', error));

					const forced = await findKitForDelivery({
						userId: profile.userId,
						reference: own.title
					});
					if (forced) {
						const delivery = await deliverKitToWhatsapp({ phone, kit: forced });
						return json(
							{
								ok: delivery.sent > 0,
								intent: 'document_request',
								user_id: profile.userId,
								kit_id: forced.kitId,
								job_title: forced.jobTitle,
								forced: true,
								...delivery
							},
							{ status: 200 }
						);
					}
				}
			}

			if (!kit) {
				const available = await recentJobTitles(profile.userId);
				await replyMissingKit(phone, available);
				return json(
					{
						ok: false,
						intent: 'document_request',
						error: 'kit_not_found',
						reference: request.reference,
						available
					},
					{ status: 200 }
				);
			}

			const delivery = await deliverKitToWhatsapp({ phone, kit });
			return json(
				{
					ok: delivery.sent > 0,
					intent: 'document_request',
					user_id: profile.userId,
					kit_id: kit.kitId,
					job_title: kit.jobTitle,
					...delivery
				},
				{ status: 200 }
			);
		}
	}

	const job = image_base64
		? await parseImageJob(image_base64, MIMETYPES.has(mimetype ?? '') ? mimetype! : 'image/jpeg')
		: await parseTextJob(text!);

	if (!job) {
		return json({ ok: true, parsed: null, reason: 'not_a_job_posting' }, { status: 200 });
	}

	const sourceUrl = `https://wa.mikeyverse.co.zw/job/${crypto.randomUUID()}`;
	let upserted: Awaited<ReturnType<typeof upsertAgentJobs>>;
	try {
		upserted = await upsertAgentJobs([
			{
				...job,
				source: 'whatsapp',
				source_url: sourceUrl,
				// A job a user forwarded is theirs alone; it must never appear in
				// another user's matches.
				owner_user_id: profile.userId
			}
		]);
	} catch (error) {
		return json(
			{
				ok: false,
				stage: 'upsert',
				error: error instanceof Error ? error.message : String(error)
			},
			{ status: 500 }
		);
	}
	if (upserted.error) {
		return json({ ok: false, parsed: job, error: upserted.error }, { status: 400 });
	}
	const jobRows = await db
		.select({ id: jobs.id })
		.from(jobs)
		.where(eq(jobs.sourceUrl, sourceUrl))
		.limit(1);
	const jobRow = jobRows[0];

	const matched = await triggerMatchingForUser({
		userId: profile.userId,
		legacyUserId: profile.legacyUserId,
		// Match only the job this user just sent, never the whole backlog.
		jobIds: jobRow ? [jobRow.id] : undefined
	});

	// A WhatsApp JD is expected to produce an application straight away, so this
	// job is generated on its own instead of waiting for the 3-hourly sweep that
	// only picks the single best-scoring match. Generation is awaited rather than
	// handed to waitUntil, which only extends the request by ~30s after the
	// response and could truncate a render.
	let generating = false;
	let delivered = 0;
	if (jobRow) {
		const match = await waitForMatch(db, profile.userId, jobRow.id);
		if (match?.status === 'matched') {
			generating = true;
			await generateForMatchedJob(profile.userId, {
				jobIds: [jobRow.id],
				allowSend: true
			}).catch((error) => console.error('WhatsApp generation failed', error));

			// Send the finished documents back to the sender. They asked for this
			// job from WhatsApp, so waiting for them to come to the dashboard would
			// be a worse experience than handing the files over here.
			const sender = parsed.data.sender;
			if (sender) {
				try {
					const kit = await findKitForDelivery({
						userId: profile.userId,
						reference: job.title
					});
					if (kit) {
						const delivery = await deliverKitToWhatsapp({ phone: sender, kit });
						delivered = delivery.sent;
						if (delivery.sent < delivery.files) {
							console.error('WhatsApp delivery incomplete', delivery);
						}
					}
				} catch (error) {
					console.error('WhatsApp delivery failed', error);
				}
			}
		}
	}

	return json(
		{
			ok: true,
			parsed: job,
			user_id: profile.userId,
			job: { id: jobRow?.id ?? null, source_url: sourceUrl, inserted: upserted.inserted },
			matched,
			generating,
			delivered
		},
		{ status: 202 }
	);
};

/**
 * The matcher runs out-of-band, so wait briefly for its row to appear before
 * generating. Returns null when the match never lands (service down or slow).
 */
async function waitForMatch(
	db: Awaited<ReturnType<typeof getDb>>,
	userId: string,
	jobId: number,
	timeoutMs = 60_000
): Promise<{ id: string; status: string } | null> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		const rows = await db
			.select({ id: jobMatches.id, status: jobMatches.status })
			.from(jobMatches)
			.where(and(eq(jobMatches.userId, userId), eq(jobMatches.jobId, jobId)))
			.limit(1);
		if (rows[0]) return rows[0];
		await new Promise((resolve) => setTimeout(resolve, 2500));
	}
	return null;
}
