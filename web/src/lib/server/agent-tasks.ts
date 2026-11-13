import { and, eq, sql } from 'drizzle-orm';
import { getDb } from './db';
import { agentTasks, jobs } from './db/schema';
import { agentRows } from './agent-auth';

type AgentTaskRow = {
	id: string;
	kind: string;
	payload: Record<string, unknown>;
	attempts: number;
	lease_expires_at: string | null;
};

export async function createAgentTask(kind: string, payload: Record<string, unknown>) {
	const db = await getDb();
	const id = crypto.randomUUID();
	await db.insert(agentTasks).values({ id, kind, payload });
	return { id, kind, status: 'pending' };
}

const LEASE_MINUTES: Record<string, number> = {
	scrape: 60,
	apply: 15
};

export async function claimAgentTask(agentId: string, kind: string, ownerUserId: string | null) {
	const db = await getDb();
	const leaseMinutes = LEASE_MINUTES[kind] ?? 15;

	// An apply task may only be claimed by an agent bound to the user it belongs
	// to, otherwise one account's agent could send email as another.
	if (kind === 'apply' && !ownerUserId) return null;

	const ownership =
		kind === 'apply'
			? sql`and (
					payload->>'web_user_id' = ${ownerUserId}
					or (payload->>'web_user_id' is null and exists (
						select 1 from profiles p
						where p.user_id = ${ownerUserId}
						  and p.legacy_user_id = payload->>'legacy_user_id'
					))
				)`
			: sql``;

	const result = await db.execute(sql`
		with candidate as (
			select id from agent_tasks
			where kind = ${kind}
			  and (
			    status = 'pending'
			    or (status = 'claimed' and lease_expires_at < now() and attempts < 3)
			  )
			  ${ownership}
			order by created_at
			for update skip locked
			limit 1
		)
		update agent_tasks t
		set status = 'claimed',
		    agent_id = ${agentId},
		    claimed_at = now(),
		    lease_expires_at = now() + make_interval(mins => ${leaseMinutes}),
		    attempts = attempts + 1
		from candidate
		where t.id = candidate.id
		returning t.id, t.kind, t.payload, t.attempts, t.lease_expires_at
	`);
	const rows = agentRows<AgentTaskRow>(result);
	const row = rows[0];
	if (!row) return null;
	return {
		id: row.id,
		kind: row.kind,
		payload: row.payload,
		attempts: row.attempts,
		leaseExpiresAt: row.lease_expires_at
	};
}

export async function completeAgentTask(
	taskId: string,
	agentId: string,
	status: 'completed' | 'failed',
	result: Record<string, unknown>
) {
	const db = await getDb();
	await db
		.update(agentTasks)
		.set({ status, result, completedAt: new Date() })
		.where(and(eq(agentTasks.id, taskId), eq(agentTasks.agentId, agentId)));
	return { id: taskId, status };
}

type IncomingJob = {
	source?: unknown;
	source_url?: unknown;
	title?: unknown;
	company?: unknown;
	location?: unknown;
	description?: unknown;
	job_type?: unknown;
	compensation?: unknown;
	date_posted?: unknown;
	expires?: unknown;
	category?: unknown;
	remote?: unknown;
	apply_instructions?: unknown;
	owner_user_id?: unknown;
};

function str(value: unknown, max: number): string | null {
	if (typeof value !== 'string') return null;
	const trimmed = value.trim();
	if (!trimmed || trimmed === 'nan' || trimmed === 'NaN') return null;
	return trimmed.slice(0, max);
}

function dateStr(value: unknown): string | null {
	if (typeof value !== 'string') return null;
	const trimmed = value.trim().slice(0, 10);
	return /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? trimmed : null;
}

export async function upsertAgentJobs(incoming: unknown) {
	if (!Array.isArray(incoming)) {
		return { inserted: 0, skipped: 0, error: 'jobs must be an array' };
	}
	if (incoming.length > 500) {
		return { inserted: 0, skipped: 0, error: 'too many jobs in one result (max 500)' };
	}

	const rows = [];
	let skipped = 0;
	for (const raw of incoming as IncomingJob[]) {
		const sourceUrl = str(raw.source_url, 2000);
		if (!sourceUrl) {
			skipped += 1;
			continue;
		}
		rows.push({
			id: sql`nextval('jobs_id_seq')`,
			source: str(raw.source, 50),
			sourceUrl,
			title: str(raw.title, 500),
			company: str(raw.company, 300),
			location: str(raw.location, 300),
			description: str(raw.description, 100_000),
			jobType: str(raw.job_type, 100),
			compensation: str(raw.compensation, 200),
			datePosted: dateStr(raw.date_posted),
			expires: dateStr(raw.expires),
			category: str(raw.category, 200),
			remote: str(raw.remote, 100),
			applyInstructions: str(raw.apply_instructions, 20_000),
			ownerUserId: str(raw.owner_user_id, 100),
			scrapedAt: new Date()
		});
	}

	if (rows.length === 0) return { inserted: 0, skipped, error: null };

	const db = await getDb();
	for (let index = 0; index < rows.length; index += 100) {
		const batch = rows.slice(index, index + 100);
		await db
			.insert(jobs)
			.values(batch)
			.onConflictDoUpdate({
				target: jobs.sourceUrl,
				set: {
					source: sql`excluded.source`,
					title: sql`excluded.title`,
					company: sql`excluded.company`,
					location: sql`excluded.location`,
					description: sql`excluded.description`,
					jobType: sql`excluded.job_type`,
					compensation: sql`excluded.compensation`,
					datePosted: sql`excluded.date_posted`,
					expires: sql`excluded.expires`,
					category: sql`excluded.category`,
					remote: sql`excluded.remote`,
					applyInstructions: sql`excluded.apply_instructions`,
					ownerUserId: sql`coalesce(excluded.owner_user_id, ${jobs.ownerUserId})`,
					scrapedAt: sql`excluded.scraped_at`
				}
			});
	}

	return { inserted: rows.length, skipped, error: null };
}
