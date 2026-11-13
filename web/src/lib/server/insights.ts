import { sql } from 'drizzle-orm';
import { getDb } from './db';
import { familySql, isCategorySql, jobTypeSql, ROLE_FAMILIES } from './job-taxonomy';

/**
 * Market aggregates for /insights.
 *
 * All grouping goes through job-taxonomy.ts so board noise (employer names in
 * the category column, descriptions pasted into job_type) does not leak into
 * the numbers.
 */

export type SupplyRow = {
	family: string;
	jobs: number;
	share: number;
	medianScore: number | null;
	medianFitNote: string | null;
};

export type MarketSnapshot = {
	totals: {
		jobs: number;
		live: number;
		last7d: number;
		last30d: number;
		remoteShare: number;
		withSalary: number;
		expired: number;
		categorisedShare: number;
	};
	bySource: Array<{ source: string; jobs: number; live: number; last7d: number }>;
	byFamily: SupplyRow[];
	byType: Array<{ label: string; jobs: number }>;
	topCompanies: Array<{ company: string; jobs: number }>;
	weeklyVolume: Array<{ week: string; jobs: number }>;
	freshness: { medianDaysListed: number | null; medianDaysToExpiry: number | null };
};

export type FunnelRow = {
	source: string;
	matches: number;
	matched: number;
	generated: number;
	applied: number;
	rejected: number;
	duplicate: number;
	appliedRate: number;
};

export type OwnerAnalytics = {
	funnel: FunnelRow[];
	scoreBands: Array<{ band: string; jobs: number }>;
	weeklyMatches: Array<{ week: string; matches: number; applied: number }>;
	documents: Array<{ type: string; count: number }>;
	totals: { matches: number; applied: number; documents: number; kits: number };
};

type Row = Record<string, unknown>;

function rows<T = Row>(result: unknown): T[] {
	if (Array.isArray(result)) return result as T[];
	if (result && typeof result === 'object' && 'rows' in result) {
		return ((result as { rows?: T[] }).rows ?? []) as T[];
	}
	return [];
}

function num(value: unknown): number {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : 0;
}

export async function getMarketSnapshot(): Promise<MarketSnapshot> {
	const db = await getDb();

	const totals = rows(
		await db.execute(sql`
			select
				count(*)::int as jobs,
				count(*) filter (where expires is null or expires >= current_date)::int as live,
				count(*) filter (where scraped_at >= now() - interval '7 days')::int as last7,
				count(*) filter (where scraped_at >= now() - interval '30 days')::int as last30,
				count(*) filter (where lower(coalesce(remote, '')) = 'remote')::int as remote,
				count(*) filter (where compensation is not null and compensation <> '' and compensation <> 'NaN')::int as with_salary,
				count(*) filter (where expires is not null and expires < current_date)::int as expired,
				count(*) filter (where ${isCategorySql()})::int as categorised
			from jobs
		`)
	)[0] as Row | undefined;

	const bySource = rows<{ source: string; jobs: number; live: number; last7d: number }>(
		await db.execute(sql`
			select coalesce(source, 'unknown') as source,
			       count(*)::int as jobs,
			       count(*) filter (where expires is null or expires >= current_date)::int as live,
			       count(*) filter (where scraped_at >= now() - interval '7 days')::int as last7
			from jobs
			group by 1
			order by jobs desc
		`)
	);

	const familyRows = rows<{ family: string; jobs: number }>(
		await db.execute(sql`
			select ${familySql()} as family, count(*)::int as jobs
			from jobs
			where ${isCategorySql()}
			group by 1
			order by jobs desc
		`)
	);

	const scores = rows<{ family: string; median_score: number }>(
		await db.execute(sql`
			select ${familySql(sql`j.category`)} as family,
			       percentile_cont(0.5) within group (order by m.score)::int as median_score
			from job_matches m
			join jobs j on j.id = m.job_id
			where m.score is not null and ${isCategorySql(sql`j.category`)}
			group by 1
		`)
	);
	const scoreByFamily = new Map(scores.map((row) => [row.family, num(row.median_score)]));

	const byType = rows<{ label: string; jobs: number }>(
		await db.execute(sql`
			select ${jobTypeSql()} as label, count(*)::int as jobs
			from jobs
			group by 1
			order by jobs desc
		`)
	);

	const topCompanies = rows<{ company: string; jobs: number }>(
		await db.execute(sql`
			select company, count(*)::int as jobs
			from jobs
			where company is not null and company not in ('NaN', 'nan', '')
			group by 1
			order by jobs desc
			limit 10
		`)
	);

	const weeklyVolume = rows<{ week: string; jobs: number }>(
		await db.execute(sql`
			select to_char(date_trunc('week', scraped_at), 'YYYY-MM-DD') as week, count(*)::int as jobs
			from jobs
			where scraped_at >= now() - interval '12 weeks'
			group by 1
			order by 1
		`)
	);

	const freshness = (rows(
		await db.execute(sql`
			select
				percentile_cont(0.5) within group (
					order by extract(epoch from (now() - scraped_at)) / 86400
				)::numeric(10,1) as median_days_listed,
				percentile_cont(0.5) within group (
					order by (expires - coalesce(date_posted, scraped_at::date))
				)::numeric(10,1) as median_days_to_expiry
			from jobs
			where expires is not null
		`)
	)[0] ?? {}) as Row;

	const totalJobs = num(totals?.jobs);
	const categorised = num(totals?.categorised);

	const orderedFamilies = ROLE_FAMILIES.map((family) => {
		const match = familyRows.find((row) => row.family === family);
		const jobs = num(match?.jobs);
		const medianScore = scoreByFamily.get(family) ?? null;
		return {
			family,
			jobs,
			share: categorised ? Math.round((jobs / categorised) * 100) : 0,
			medianScore,
			medianFitNote: null
		};
	})
		.filter((row) => row.jobs > 0)
		.sort((a, b) => b.jobs - a.jobs);

	return {
		totals: {
			jobs: totalJobs,
			live: num(totals?.live),
			last7d: num(totals?.last7),
			last30d: num(totals?.last30),
			remoteShare: totalJobs ? Math.round((num(totals?.remote) / totalJobs) * 100) : 0,
			withSalary: num(totals?.with_salary),
			expired: num(totals?.expired),
			categorisedShare: totalJobs ? Math.round((categorised / totalJobs) * 100) : 0
		},
		bySource,
		byFamily: orderedFamilies,
		byType,
		topCompanies,
		weeklyVolume,
		freshness: {
			medianDaysListed: freshness.median_days_listed != null
				? num(freshness.median_days_listed)
				: null,
			medianDaysToExpiry: freshness.median_days_to_expiry != null
				? num(freshness.median_days_to_expiry)
				: null
		}
	};
}

export async function getOwnerAnalytics(): Promise<OwnerAnalytics> {
	const db = await getDb();

	const funnel = rows<Row>(
		await db.execute(sql`
			select coalesce(j.source, 'unknown') as source,
			       count(*)::int as matches,
			       count(*) filter (where m.status = 'matched')::int as matched,
			       count(*) filter (where m.status = 'generated')::int as generated,
			       count(*) filter (where m.status = 'applied')::int as applied,
			       count(*) filter (where m.status = 'rejected')::int as rejected,
			       count(*) filter (where m.status = 'duplicate')::int as duplicate
			from job_matches m
			join jobs j on j.id = m.job_id
			group by 1
			order by matches desc
		`)
	);

	const scoreBands = rows<{ band: string; jobs: number }>(
		await db.execute(sql`
			select case
			         when score >= 85 then '85-100'
			         when score >= 70 then '70-84'
			         when score >= 55 then '55-69'
			         when score >= 40 then '40-54'
			         else 'Below 40'
			       end as band,
			       count(*)::int as jobs
			from job_matches
			where score is not null
			group by 1
		`)
	);

	const weeklyMatches = rows<{ week: string; matches: number; applied: number }>(
		await db.execute(sql`
			select to_char(date_trunc('week', created_at), 'YYYY-MM-DD') as week,
			       count(*)::int as matches,
			       count(*) filter (where status = 'applied')::int as applied
			from job_matches
			where created_at >= now() - interval '12 weeks'
			group by 1
			order by 1
		`)
	);

	const documents = rows<{ type: string; count: number }>(
		await db.execute(sql`
			select document_type as type, count(*)::int as count
			from documents
			group by 1
			order by count desc
		`)
	);

	const totals = (rows(
		await db.execute(sql`
			select
				(select count(*)::int from job_matches) as matches,
				(select count(*)::int from job_matches where status = 'applied') as applied,
				(select count(*)::int from documents) as documents,
				(select count(*)::int from application_kits) as kits
		`)
	)[0] ?? {}) as Row;

	const bandOrder = ['85-100', '70-84', '55-69', '40-54', 'Below 40'];

	return {
		funnel: funnel.map((row) => ({
			source: String(row.source),
			matches: num(row.matches),
			matched: num(row.matched),
			generated: num(row.generated),
			applied: num(row.applied),
			rejected: num(row.rejected),
			duplicate: num(row.duplicate),
			appliedRate: num(row.matches)
				? Math.round((num(row.applied) / num(row.matches)) * 1000) / 10
				: 0
		})),
		scoreBands: scoreBands.sort(
			(a, b) => bandOrder.indexOf(a.band) - bandOrder.indexOf(b.band)
		),
		weeklyMatches,
		documents,
		totals: {
			matches: num(totals.matches),
			applied: num(totals.applied),
			documents: num(totals.documents),
			kits: num(totals.kits)
		}
	};
}
