import { envValue } from './env';

export async function triggerMatchingForUser(input: {
	userId: string;
	legacyUserId?: string | null;
	matchSince?: Date | null;
	/** Restrict the run to these jobs, so only this user is matched to them. */
	jobIds?: number[];
}): Promise<boolean> {
	const target = envValue('MATCH_TRIGGER_URL');
	const secret = envValue('MATCH_TRIGGER_SECRET');
	if (!target || !secret) return false;

	try {
		const response = await fetch(target, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-match-trigger-secret': secret
			},
			body: JSON.stringify({
				user_id: input.legacyUserId ?? input.userId,
				web_user_id: input.userId,
				legacy_user_id: input.legacyUserId ?? null,
				match_since: input.matchSince?.toISOString() ?? null,
				job_ids: input.jobIds ?? null,
				limit: 50
			}),
			signal: AbortSignal.timeout(15000)
		});
		return response.ok;
	} catch {
		return false;
	}
}
