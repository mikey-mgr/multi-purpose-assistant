import type { NeonHttpDatabase } from 'drizzle-orm/neon-http';
import type { PostgresJsDatabase } from 'drizzle-orm/postgres-js';
import { envValue } from '../env';
import * as schema from './schema';

export type Database = NeonHttpDatabase<typeof schema> | PostgresJsDatabase<typeof schema>;

const globalForDb = globalThis as typeof globalThis & {
	__mukanaDb?: Promise<Database>;
};

async function createDb(): Promise<Database> {
	const url = envValue('DATABASE_URL');
	if (!url) {
		throw new Error('DATABASE_URL is not configured');
	}

	if (envValue('DATABASE_DRIVER') === 'neon') {
		const [{ drizzle }, { neon }] = await Promise.all([
			import('drizzle-orm/neon-http'),
			import('@neondatabase/serverless')
		]);
		return drizzle(neon(url), { schema });
	}

	const [{ drizzle }, postgres] = await Promise.all([
		import('drizzle-orm/postgres-js'),
		import('postgres')
	]);
	const client = postgres.default(url, { max: 5, prepare: false });
	return drizzle(client, { schema });
}

export function getDb(): Promise<Database> {
	if (!globalForDb.__mukanaDb) {
		globalForDb.__mukanaDb = createDb();
	}
	return globalForDb.__mukanaDb;
}
