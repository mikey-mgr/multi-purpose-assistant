import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { documents, profiles } from '../../../../lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { desc } from 'drizzle-orm';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';
import { generateBaseCv, isCvTemplate } from '../../../../lib/server/resume/base-cv';

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const db = await getDb();
	const rows = await db
		.select({
			id: documents.id,
			promptName: documents.promptName,
			createdAt: documents.createdAt,
			rendercvYaml: documents.rendercvYaml
		})
		.from(documents)
		.where(eq(documents.userId, event.locals.user.id))
		.orderBy(desc(documents.createdAt))
		.limit(200);

	const baseCvs = rows
		.filter((row) => row.promptName === 'base_cv' || row.promptName === 'base_cv_polished')
		.map((row) => {
			let theme: string | null = null;
			try {
				theme = JSON.parse(row.rendercvYaml ?? '{}')?.design?.theme ?? null;
			} catch {
				theme = null;
			}
			return {
				id: row.id,
				theme,
				polished: row.promptName === 'base_cv_polished',
				createdAt: row.createdAt
			};
		});

	return json({ versions: baseCvs }, { headers: { 'Cache-Control': 'no-store' } });
};

export const POST: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'base-cv:generate'), 12, 3600);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: { theme?: unknown; polish?: unknown } = {};
	try {
		body = (await event.request.json()) as { theme?: unknown; polish?: unknown };
	} catch {
		body = {};
	}

	const db = await getDb();
	const profileRows = await db
		.select({ cvTemplate: profiles.cvTemplate })
		.from(profiles)
		.where(eq(profiles.userId, event.locals.user.id))
		.limit(1);

	const requested = typeof body.theme === 'string' ? body.theme : null;
	const fallback = profileRows[0]?.cvTemplate ?? 'harvard';
	const theme = requested && isCvTemplate(requested) ? requested : fallback;

	const outcome = await generateBaseCv({
		userId: event.locals.user.id,
		theme,
		polish: body.polish !== false
	});

	if (!outcome.result) {
		return json({ error: outcome.error ?? 'Could not generate your CV' }, { status: 400 });
	}

	return json(outcome.result, { status: 201 });
};
