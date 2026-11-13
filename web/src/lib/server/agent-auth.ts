import type { RequestEvent } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { getDb } from './db';
import { agents } from './db/schema';
import { randomToken, sha256Hex, timingSafeEqual } from './crypto';
import { envValue } from './env';

export type AgentKind = 'scraper' | 'apply' | 'both';

const KINDS: AgentKind[] = ['scraper', 'apply', 'both'];

export function isAgentKind(value: string): value is AgentKind {
	return KINDS.includes(value as AgentKind);
}

export function bootstrapAuthorized(event: RequestEvent): boolean {
	const expected = envValue('AGENT_BOOTSTRAP_SECRET');
	const provided = event.request.headers.get('x-agent-bootstrap-secret');
	if (!expected || !provided) return false;
	return timingSafeEqual(expected, provided);
}

export async function createAgent(name: string, kind: AgentKind, userId: string | null = null) {
	const key = randomToken(32);
	const keyHash = await sha256Hex(key);
	const db = await getDb();
	const id = crypto.randomUUID();
	await db.insert(agents).values({ id, name, kind, keyHash, userId });
	return { agent: { id, name, kind }, agentKey: key };
}

export async function authenticateAgent(
	event: RequestEvent,
	allowedKinds: AgentKind[] = ['scraper', 'apply', 'both']
) {
	const agentId = event.request.headers.get('x-agent-id');
	const agentKey = event.request.headers.get('x-agent-key');
	if (!agentId || !agentKey) return null;

	const db = await getDb();
	const rows = await db.select().from(agents).where(eq(agents.id, agentId)).limit(1);
	const agent = rows[0];
	if (!agent || agent.status !== 'active') return null;
	if (agent.kind !== 'both' && !allowedKinds.includes(agent.kind as AgentKind)) return null;

	const expected = agent.keyHash;
	const actual = await sha256Hex(agentKey);
	if (!timingSafeEqual(expected, actual)) return null;

	await db.update(agents).set({ lastSeenAt: new Date() }).where(eq(agents.id, agent.id));
	return agent;
}

export function agentRateKey(agentId: string, scope: string) {
	return `agent:${agentId}:${scope}`;
}

export function agentRows<T>(result: unknown): T[] {
	if (Array.isArray(result)) return result as T[];
	if (result && typeof result === 'object' && 'rows' in result) {
		const rows = (result as { rows?: unknown }).rows;
		if (Array.isArray(rows)) return rows as T[];
	}
	return [];
}
