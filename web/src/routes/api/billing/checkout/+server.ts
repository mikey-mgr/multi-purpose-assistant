import { json } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { deviceProfiles, payments } from '../../../../lib/server/db/schema';
import {
	getOrCreatePricing,
	type DeviceBucket
} from '../../../../lib/server/pricing';
import {
	initiatePaynowPayment,
	newPaymentReference
} from '../../../../lib/server/paynow';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';

const BUCKETS: DeviceBucket[] = ['low', 'mid', 'high', 'premium'];

const checkoutInput = z
	.object({
		plan: z.enum(['pro', 'byok'])
	})
	.strict();

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'billing:checkout'), 10, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = checkoutInput.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid plan' }, { status: 400 });
	}

	const country = (event.request.headers.get('cf-ipcountry') ?? 'ZW').toUpperCase();
	const db = await getDb();
	const latestDevice = await db
		.select()
		.from(deviceProfiles)
		.where(eq(deviceProfiles.userId, event.locals.user.id))
		.orderBy(desc(deviceProfiles.createdAt))
		.limit(1);
	const bucket = BUCKETS.includes(latestDevice[0]?.bucket as DeviceBucket)
		? (latestDevice[0].bucket as DeviceBucket)
		: 'mid';

	const pricing = await getOrCreatePricing(event.locals.user.id, country, bucket);
	const amountCents = parsed.data.plan === 'pro' ? pricing.pro : pricing.byok;
	const reference = newPaymentReference();

	await db.insert(payments).values({
		userId: event.locals.user.id,
		reference,
		plan: parsed.data.plan,
		amountCents,
		currency: pricing.currency,
		status: 'created'
	});

	let init: Awaited<ReturnType<typeof initiatePaynowPayment>>;
	try {
		init = await initiatePaynowPayment({
			reference,
			amountCents,
			additionalInfo: `Mukana ${parsed.data.plan.toUpperCase()} subscription`,
			email: event.locals.user.email
		});
	} catch {
		await db
			.update(payments)
			.set({ status: 'failed', updatedAt: new Date() })
			.where(eq(payments.reference, reference));
		return json({ error: 'Could not start the Paynow transaction', reference }, { status: 502 });
	}

	await db
		.update(payments)
		.set({
			status: init.ok ? 'pending' : 'failed',
			pollUrl: init.pollUrl,
			raw: init.raw,
			updatedAt: new Date()
		})
		.where(eq(payments.reference, reference));

	if (!init.ok || !init.browserUrl) {
		return json(
			{
				error: init.error ?? 'Paynow could not start the transaction',
				reference
			},
			{ status: 502 }
		);
	}

	return json({
		reference,
		plan: parsed.data.plan,
		amountCents,
		currency: pricing.currency,
		checkoutUrl: init.browserUrl,
		pollUrl: init.pollUrl,
		instructions: init.instructions
	});
};
