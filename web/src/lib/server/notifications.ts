import { and, desc, eq, gte } from 'drizzle-orm';
import { getDb } from './db';
import { jobMatches, jobs, whatsappMessages, whatsappPilot } from './db/schema';
import { normalizePhone, sendWhatsappText } from './whatsapp';

export async function notifyNewMatches(userId: string, since: Date): Promise<void> {
	const db = await getDb();
	const pilot = await db
		.select({ phone: whatsappPilot.phone })
		.from(whatsappPilot)
		.where(and(eq(whatsappPilot.userId, userId), eq(whatsappPilot.status, 'active')))
		.limit(1);

	if (!pilot[0]?.phone) return;

	const rows = await db
		.select({
			id: jobMatches.id,
			title: jobs.title,
			company: jobs.company,
			score: jobMatches.score,
			status: jobMatches.status
		})
		.from(jobMatches)
		.innerJoin(jobs, eq(jobMatches.jobId, jobs.id))
		.where(
			and(
				eq(jobMatches.userId, userId),
				eq(jobMatches.status, 'matched'),
				gte(jobMatches.createdAt, since)
			)
		)
		.orderBy(desc(jobMatches.score))
		.limit(5);

	if (rows.length === 0) return;

	const lines = [
		`Mukana: ${rows.length} new match${rows.length === 1 ? '' : 'es'} for you`,
		...rows.map(
			(row, index) =>
				`${index + 1}. ${row.title ?? 'Job'} at ${row.company ?? 'Company'}${row.score != null ? ` (${row.score}%)` : ''}`
		),
		'',
		`Open https://mukana.mikeyverse.co.zw/matches?status=active#match-${rows[0].id}`
	];

	const body = lines.join('\n');
	const phone = normalizePhone(pilot[0].phone);
	const sent = await sendWhatsappText(phone, body);

	await db.insert(whatsappMessages).values({
		userId,
		phone,
		direction: 'outbound',
		body,
		raw: { sent }
	});
}
