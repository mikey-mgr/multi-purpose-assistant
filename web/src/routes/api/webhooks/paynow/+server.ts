import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { payments, subscriptions } from '../../../../lib/server/db/schema';
import { verifyPaynowEntries } from '../../../../lib/server/paynow';

type Entry = [string, string];

function parseEntries(value: unknown): Entry[] | null {
	if (!Array.isArray(value)) return null;
	const entries: Entry[] = [];
	for (const item of value) {
		if (
			!Array.isArray(item) ||
			item.length !== 2 ||
			typeof item[0] !== 'string' ||
			typeof item[1] !== 'string'
		) {
			return null;
		}
		entries.push([item[0], item[1]]);
	}
	return entries;
}

async function readEntries(request: Request): Promise<Entry[] | null> {
	const contentType = request.headers.get('content-type') ?? '';
	if (contentType.includes('application/json')) {
		try {
			const body = (await request.json()) as { entries?: unknown };
			return parseEntries(body.entries);
		} catch {
			return null;
		}
	}

	try {
		const form = await request.formData();
		return Array.from(form.entries()).filter(
			(entry): entry is Entry => typeof entry[1] === 'string'
		);
	} catch {
		return null;
	}
}

function normaliseStatus(value: string | undefined): string {
	return (value ?? 'unknown').trim().toLowerCase();
}

export const POST: RequestHandler = async (event) => {
	const entries = await readEntries(event.request);
	if (!entries) {
		return new Response('Invalid payload', { status: 400 });
	}

	const valid = await verifyPaynowEntries(entries);
	if (!valid) {
		return new Response('Invalid hash', { status: 400 });
	}

	const raw: Record<string, string> = {};
	for (const [key, value] of entries) raw[key.toLowerCase()] = value;

	const reference = raw.reference;
	if (!reference) {
		return new Response('Missing reference', { status: 400 });
	}

	const db = await getDb();
	const existing = await db
		.select()
		.from(payments)
		.where(eq(payments.reference, reference))
		.limit(1);

	if (!existing[0]) {
		return new Response('Unknown reference', { status: 404 });
	}

	const status = normaliseStatus(raw.status);
	const paid = status === 'paid' || status === 'awaiting delivery' || status === 'delivered';
	const failed = status === 'cancelled' || status === 'refunded';

	if (paid && raw.amount) {
		const amountCents = Math.round(Number(raw.amount) * 100);
		if (!Number.isFinite(amountCents) || amountCents !== existing[0].amountCents) {
			return new Response('Amount mismatch', { status: 400 });
		}
	}

	await db
		.update(payments)
		.set({
			status,
			paynowReference: raw.paynowreference ?? existing[0].paynowReference,
			pollUrl: raw.pollurl ?? existing[0].pollUrl,
			raw,
			updatedAt: new Date(),
			paidAt: paid ? existing[0].paidAt ?? new Date() : existing[0].paidAt
		})
		.where(eq(payments.reference, reference));

	if (paid || failed) {
		const now = new Date();
		const periodEnd = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
		await db
			.insert(subscriptions)
			.values({
				userId: existing[0].userId,
				plan: paid ? existing[0].plan : 'free',
				status: paid ? 'active' : 'cancelled',
				currentPeriodEnd: paid ? periodEnd : null,
				updatedAt: now
			})
			.onConflictDoUpdate({
				target: subscriptions.userId,
				set: {
					plan: paid ? existing[0].plan : 'free',
					status: paid ? 'active' : 'cancelled',
					currentPeriodEnd: paid ? periodEnd : null,
					updatedAt: now
				}
			});
	}

	return new Response('OK', { status: 200 });
};
