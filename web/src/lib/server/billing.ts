import { and, eq } from 'drizzle-orm';
import { getDb } from './db';
import { payments, subscriptions } from './db/schema';

export async function markMockPaymentPaid(userId: string, reference: string) {
	const db = await getDb();
	const payment = await db
		.select()
		.from(payments)
		.where(and(eq(payments.reference, reference), eq(payments.userId, userId)))
		.limit(1);

	if (!payment[0]) return null;

	const now = new Date();
	const periodEnd = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

	await db
		.update(payments)
		.set({ status: 'paid', paidAt: payment[0].paidAt ?? now, updatedAt: now })
		.where(eq(payments.reference, payment[0].reference));

	await db
		.insert(subscriptions)
		.values({
			userId,
			plan: payment[0].plan,
			status: 'active',
			currentPeriodEnd: periodEnd,
			updatedAt: now
		})
		.onConflictDoUpdate({
			target: subscriptions.userId,
			set: {
				plan: payment[0].plan,
				status: 'active',
				currentPeriodEnd: periodEnd,
				updatedAt: now
			}
		});

	return payment[0];
}
