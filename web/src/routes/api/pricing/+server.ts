import { json } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { deviceProfiles } from '../../../lib/server/db/schema';
import {
	formatPrice,
	getOrCreatePricing,
	type DeviceBucket
} from '../../../lib/server/pricing';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

const BUCKETS: DeviceBucket[] = ['low', 'mid', 'high', 'premium'];

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'pricing:get'), 60, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const country = (event.request.headers.get('cf-ipcountry') ?? 'ZW').toUpperCase();
	const db = await getDb();
	const latest = await db
		.select()
		.from(deviceProfiles)
		.where(eq(deviceProfiles.userId, event.locals.user.id))
		.orderBy(desc(deviceProfiles.createdAt))
		.limit(1);

	const bucket = BUCKETS.includes(latest[0]?.bucket as DeviceBucket)
		? (latest[0].bucket as DeviceBucket)
		: 'mid';

	const pricing = await getOrCreatePricing(event.locals.user.id, country, bucket, {
		persist: Boolean(latest[0])
	});

	return json(
		{
			country,
			bucket,
			variant: pricing.variant,
			currency: pricing.currency,
			pro: {
				amountCents: pricing.pro,
				formatted: formatPrice(pricing.pro, pricing.currency)
			},
			byok: {
				amountCents: pricing.byok,
				formatted: formatPrice(pricing.byok, pricing.currency)
			}
		},
		{
			headers: {
				'Cache-Control': 'no-store',
				'X-RateLimit-Limit': String(limit.limit),
				'X-RateLimit-Remaining': String(limit.remaining)
			}
		}
	);
};
