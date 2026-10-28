import { json } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../lib/server/db';
import { deviceProfiles } from '../../../lib/server/db/schema';
import {
	formatPrice,
	getOrCreatePricing,
	scoreDevice,
	type DeviceSignals
} from '../../../lib/server/pricing';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../lib/server/rate-limit';

const signalsInput = z
	.object({
		deviceMemory: z.number().min(0).max(128).optional(),
		hardwareConcurrency: z.number().int().min(0).max(256).optional(),
		devicePixelRatio: z.number().min(0).max(10).optional(),
		screenWidth: z.number().int().min(0).max(20000).optional(),
		screenHeight: z.number().int().min(0).max(20000).optional(),
		gpuTier: z.enum(['low', 'mid', 'high']).optional(),
		connectionType: z.enum(['2g', '3g', '4g', '5g', 'wifi', 'unknown']).optional(),
		osRecency: z.enum(['old', 'current-1', 'current', 'unknown']).optional(),
		deviceType: z.enum(['mobile', 'tablet', 'desktop']).optional()
	})
	.strict();

async function hashSignals(value: string) {
	const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('');
}

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'device-profile'), 20, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = signalsInput.safeParse(body);
	if (!parsed.success) {
		return json(
			{ error: 'Invalid device signals', issues: parsed.error.flatten() },
			{ status: 400 }
		);
	}

	const country = (event.request.headers.get('cf-ipcountry') ?? 'ZW').toUpperCase();
	const { score, bucket } = scoreDevice(parsed.data as DeviceSignals);
	const signalsHash = await hashSignals(JSON.stringify({ ...parsed.data, country }));

	const db = await getDb();
	await db.insert(deviceProfiles).values({
		userId: event.locals.user.id,
		score,
		bucket,
		country,
		currency: 'USD',
		signalsHash
	});

	const pricing = await getOrCreatePricing(event.locals.user.id, country, bucket);

	return json({
		bucket,
		score,
		country,
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
	});
};
