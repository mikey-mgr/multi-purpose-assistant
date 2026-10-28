import { getRequestEvent } from '$app/server';
import { betterAuth } from 'better-auth';
import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { sveltekitCookies } from 'better-auth/svelte-kit';
import { getDb } from './db';
import * as schema from './db/schema';
import { envValue } from './env';

let authPromise: Promise<Auth> | null = null;

async function createAuth() {
	const secret = envValue('BETTER_AUTH_SECRET');
	if (!secret) {
		throw new Error('BETTER_AUTH_SECRET is not configured');
	}

	const db = await getDb();
	const baseURL = envValue('BETTER_AUTH_URL') ?? 'http://localhost:5173';
	const extraOrigins = (envValue('BETTER_AUTH_TRUSTED_ORIGINS') ?? '')
		.split(',')
		.map((origin) => origin.trim())
		.filter(Boolean);
	const devOrigins = import.meta.env.DEV
		? ['http://localhost:5173', 'http://127.0.0.1:5173']
		: [];

	return betterAuth({
		appName: 'Mukana',
		baseURL,
		secret,
		trustedOrigins: [baseURL, ...extraOrigins, ...devOrigins],
		database: drizzleAdapter(db, { provider: 'pg', schema }),
		emailAndPassword: {
			enabled: true,
			minPasswordLength: 8,
			maxPasswordLength: 128,
			autoSignIn: true
		},
		session: {
			expiresIn: 60 * 60 * 24 * 30,
			updateAge: 60 * 60 * 24
		},
		advanced: {
			ipAddress: {
				ipAddressHeaders: ['cf-connecting-ip', 'x-forwarded-for', 'x-real-ip']
			}
		},
		rateLimit: {
			enabled: true,
			window: 60,
			max: 100,
			storage: 'database',
			customRules: {
				'/sign-in/email': { window: 60, max: 5 },
				'/sign-up/email': { window: 60, max: 3 },
				'/forget-password': { window: 300, max: 3 },
				'/reset-password': { window: 300, max: 5 }
			}
		},
		plugins: [sveltekitCookies(getRequestEvent)]
	});
}

export type Auth = Awaited<ReturnType<typeof createAuth>>;

export function getAuth(): Promise<Auth> {
	if (!authPromise) {
		authPromise = createAuth();
	}
	return authPromise;
}
