import { json } from '@sveltejs/kit';
import { and, desc, eq } from 'drizzle-orm';
import { z } from 'zod';
import type { RequestHandler } from './$types';
import { getDb } from '../../../../lib/server/db';
import { documents, jobMatches, jobs } from '../../../../lib/server/db/schema';
import { rateLimit, rateLimitKey, tooManyRequests } from '../../../../lib/server/rate-limit';
import { rebuildApplication } from '../../../../lib/server/resume/rebuild';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const patchInput = z
	.object({
		content: z.string().max(60000)
	})
	.strict();

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'documents:get'), 120, 60);
	if (!limit.allowed) return tooManyRequests(limit);

	const db = await getDb();
	const rows = await db
		.select({
			id: documents.id,
			documentType: documents.documentType,
			content: documents.content,
			rendercvYaml: documents.rendercvYaml,
			promptName: documents.promptName,
			model: documents.model,
			tokensUsed: documents.tokensUsed,
			createdAt: documents.createdAt,
			jobId: jobs.publicId,
			jobTitle: jobs.title,
			company: jobs.company
		})
		.from(documents)
		.leftJoin(jobs, eq(documents.jobId, jobs.id))
		.where(and(eq(documents.id, event.params.id), eq(documents.userId, event.locals.user.id)))
		.limit(1);

	if (!rows[0]) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	return json(
		{
			id: rows[0].id,
			type: rows[0].documentType,
			content: rows[0].content,
			rendercvYaml: rows[0].rendercvYaml,
			promptName: rows[0].promptName,
			model: rows[0].model,
			tokensUsed: rows[0].tokensUsed,
			createdAt: rows[0].createdAt,
			job: { id: rows[0].jobId, title: rows[0].jobTitle, company: rows[0].company }
		},
		{ headers: { 'Cache-Control': 'private, max-age=60' } }
	);
};

export const PATCH: RequestHandler = async (event) => {
	if (!event.locals.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}
	if (!UUID_RE.test(event.params.id)) {
		return json({ error: 'Not found' }, { status: 404 });
	}

	const limit = await rateLimit(rateLimitKey(event, 'documents:patch'), 20, 300);
	if (!limit.allowed) return tooManyRequests(limit);

	let body: unknown;
	try {
		body = await event.request.json();
	} catch {
		return json({ error: 'Invalid JSON body' }, { status: 400 });
	}

	const parsed = patchInput.safeParse(body);
	if (!parsed.success) {
		return json({ error: 'Invalid document', issues: parsed.error.flatten() }, { status: 400 });
	}

	const db = await getDb();
	const rows = await db
		.select()
		.from(documents)
		.where(and(eq(documents.id, event.params.id), eq(documents.userId, event.locals.user.id)))
		.limit(1);

	const document = rows[0];
	if (!document) return json({ error: 'Not found' }, { status: 404 });
	if (document.documentType === 'resume') {
		return json(
			{ error: 'CVs are rendered from structured data. Edit in the CV builder.' },
			{ status: 400 }
		);
	}

	await db
		.update(documents)
		.set({ content: parsed.data.content })
		.where(eq(documents.id, document.id));

	// Roll the saved edit into the matching application kit.
	let rebuild: Awaited<ReturnType<typeof rebuildApplication>> | null = null;
	if (document.jobId) {
		const matchRows = await db
			.select({ id: jobMatches.id })
			.from(jobMatches)
			.where(
				and(
					eq(jobMatches.userId, event.locals.user.id),
					eq(jobMatches.jobId, document.jobId)
				)
			)
			.orderBy(desc(jobMatches.createdAt))
			.limit(1);
		if (matchRows[0]) {
			rebuild = await rebuildApplication(matchRows[0].id, event.locals.user.id, {
				coverLetterOverride: parsed.data.content
			});
		}
	}

	return json({ ok: true, documentId: document.id, rebuild });
};
