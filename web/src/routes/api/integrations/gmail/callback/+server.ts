import { redirect } from '@sveltejs/kit';
import { and, eq, gt } from 'drizzle-orm';
import type { RequestHandler } from './$types';
import { encryptSecret } from '../../../../../lib/server/crypto';
import { getDb } from '../../../../../lib/server/db';
import { oauthAccounts, oauthStates } from '../../../../../lib/server/db/schema';
import {
	exchangeGmailCode,
	fetchGmailProfile,
	isGmailMock
} from '../../../../../lib/server/gmail';

export const GET: RequestHandler = async (event) => {
	const user = event.locals.user;
	if (!user) redirect(303, '/login');

	const error = event.url.searchParams.get('error');
	const code = event.url.searchParams.get('code');
	const state = event.url.searchParams.get('state');

	if (error || !code || !state) {
		redirect(303, '/settings?gmail=denied');
	}

	const db = await getDb();
	const stored = await db
		.select()
		.from(oauthStates)
		.where(
			and(
				eq(oauthStates.id, state),
				eq(oauthStates.userId, user.id),
				eq(oauthStates.provider, 'gmail'),
				gt(oauthStates.expiresAt, new Date())
			)
		)
		.limit(1);

	await db.delete(oauthStates).where(eq(oauthStates.id, state));

	if (!stored[0]) {
		redirect(303, '/settings?gmail=state');
	}

	let target = '/settings?gmail=error';

	try {
		const tokens = await exchangeGmailCode(code);
		if (!tokens.refreshToken) {
			target = '/settings?gmail=refresh';
		} else {
			const profile = await fetchGmailProfile(tokens.accessToken);
			const encrypted = await encryptSecret(tokens.refreshToken);
			const now = new Date();

			await db
				.insert(oauthAccounts)
				.values({
					userId: user.id,
					provider: 'gmail',
					email: profile.email,
					scope: tokens.scope,
					encryptedRefreshToken: encrypted.ciphertext,
					iv: encrypted.iv,
					updatedAt: now
				})
				.onConflictDoUpdate({
					target: [oauthAccounts.userId, oauthAccounts.provider],
					set: {
						email: profile.email,
						scope: tokens.scope,
						encryptedRefreshToken: encrypted.ciphertext,
						iv: encrypted.iv,
						updatedAt: now
					}
				});

			target = `/settings?gmail=${isGmailMock() ? 'mock-connected' : 'connected'}`;
		}
	} catch {
		target = '/settings?gmail=error';
	}

	redirect(303, target);
};
