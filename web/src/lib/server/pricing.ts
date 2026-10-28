import { eq } from 'drizzle-orm';
import { getDb } from './db';
import { pricingVariants } from './db/schema';

export type DeviceBucket = 'low' | 'mid' | 'high' | 'premium';

export type DeviceSignals = {
	deviceMemory?: number;
	hardwareConcurrency?: number;
	devicePixelRatio?: number;
	screenWidth?: number;
	screenHeight?: number;
	gpuTier?: 'low' | 'mid' | 'high';
	connectionType?: '2g' | '3g' | '4g' | '5g' | 'wifi' | 'unknown';
	osRecency?: 'old' | 'current-1' | 'current' | 'unknown';
	deviceType?: 'mobile' | 'tablet' | 'desktop';
};

const COUNTRY_INDEX: Record<string, number> = {
	ZW: 0.55,
	ZA: 0.7,
	ZM: 0.7,
	MW: 0.7,
	MZ: 0.7,
	BW: 0.7,
	NA: 0.7,
	KE: 0.7,
	NG: 0.7,
	GH: 0.7,
	UG: 0.7,
	TZ: 0.7,
	AE: 0.95,
	SA: 0.95,
	GB: 1,
	US: 1,
	CA: 1,
	AU: 1,
	NZ: 1,
	IE: 1,
	DE: 1,
	FR: 1,
	NL: 1
};

const DEVICE_MULTIPLIER: Record<DeviceBucket, number> = {
	low: 0.85,
	mid: 1,
	high: 1.1,
	premium: 1.2
};

const PLAN_BASE = {
	pro: { base: 1200, floor: 700, cap: 1500 },
	byok: { base: 800, floor: 400, cap: 1000 }
} as const;

function clamp(value: number, floor: number, cap: number) {
	return Math.min(cap, Math.max(floor, value));
}

function priceFor(base: number, countryIndex: number, deviceMultiplier: number) {
	return Math.round(base * countryIndex * deviceMultiplier);
}

function fnv1a(value: string): number {
	let hash = 2166136261;
	for (let i = 0; i < value.length; i += 1) {
		hash ^= value.charCodeAt(i);
		hash = Math.imul(hash, 16777619);
	}
	return hash >>> 0;
}

export function scoreDevice(signals: DeviceSignals): { score: number; bucket: DeviceBucket } {
	if (signals.deviceMemory === undefined && signals.hardwareConcurrency === undefined) {
		return { score: 50, bucket: 'mid' };
	}

	let score = 0;
	const memory = signals.deviceMemory ?? 0;
	if (memory > 8) score += 30;
	else if (memory > 4) score += 20;
	else if (memory > 2) score += 10;

	const cores = signals.hardwareConcurrency ?? 0;
	if (cores > 8) score += 22;
	else if (cores > 6) score += 16;
	else if (cores > 4) score += 8;

	const dpr = signals.devicePixelRatio ?? 0;
	if (dpr >= 3.5) score += 18;
	else if (dpr >= 3) score += 12;
	else if (dpr >= 2) score += 6;

	const area = ((signals.screenWidth ?? 0) * (signals.screenHeight ?? 0)) / 1_000_000;
	if (area >= 2) score += 12;
	else if (area >= 1) score += 8;
	else if (area >= 0.5) score += 4;

	if (signals.gpuTier === 'high') score += 16;
	else if (signals.gpuTier === 'mid') score += 8;

	if (signals.connectionType === 'wifi') score += 10;
	else if (signals.connectionType === '5g') score += 8;
	else if (signals.connectionType === '4g') score += 6;

	if (signals.osRecency === 'current') score += 8;
	else if (signals.osRecency === 'current-1') score += 4;

	if (signals.deviceType === 'desktop') score += 8;
	else if (signals.deviceType === 'tablet') score += 4;

	const normalised = Math.round((score / 124) * 100);
	const bucket: DeviceBucket =
		normalised < 25 ? 'low' : normalised < 50 ? 'mid' : normalised < 75 ? 'high' : 'premium';

	return { score: normalised, bucket };
}

export function computePrices(country: string, bucket: DeviceBucket, control = false) {
	const countryIndex = COUNTRY_INDEX[country.toUpperCase()] ?? 0.8;
	const multiplier = control ? 1 : DEVICE_MULTIPLIER[bucket];

	const pro = clamp(
		priceFor(PLAN_BASE.pro.base, countryIndex, multiplier),
		PLAN_BASE.pro.floor,
		PLAN_BASE.pro.cap
	);
	const byok = clamp(
		priceFor(PLAN_BASE.byok.base, countryIndex, multiplier),
		PLAN_BASE.byok.floor,
		PLAN_BASE.byok.cap
	);

	return { pro, byok, currency: 'USD' };
}

export async function getOrCreatePricing(
	userId: string,
	country: string,
	bucket: DeviceBucket,
	options: { persist?: boolean } = {}
) {
	const db = await getDb();
	const existing = await db
		.select()
		.from(pricingVariants)
		.where(eq(pricingVariants.userId, userId))
		.limit(1);

	if (existing[0]) {
		return {
			variant: existing[0].variant,
			pro: existing[0].pricePro,
			byok: existing[0].priceByok,
			currency: existing[0].currency
		};
	}

	const variant = fnv1a(`${userId}:price_v1`) % 100 < 20 ? 'control' : 'personalized';
	const prices = computePrices(country, bucket, variant === 'control');

	if (options.persist === false) {
		return { variant, pro: prices.pro, byok: prices.byok, currency: prices.currency };
	}

	await db
		.insert(pricingVariants)
		.values({
			userId,
			variant,
			pricePro: prices.pro,
			priceByok: prices.byok,
			currency: prices.currency
		})
		.onConflictDoNothing();

	const saved = await db
		.select()
		.from(pricingVariants)
		.where(eq(pricingVariants.userId, userId))
		.limit(1);

	const row = saved[0];
	return {
		variant: row?.variant ?? variant,
		pro: row?.pricePro ?? prices.pro,
		byok: row?.priceByok ?? prices.byok,
		currency: row?.currency ?? prices.currency
	};
}

export function formatPrice(cents: number, currency = 'USD') {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency,
		minimumFractionDigits: 2
	}).format(cents / 100);
}
