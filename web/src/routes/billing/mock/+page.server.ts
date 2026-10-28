import { error, redirect } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import { markMockPaymentPaid } from '../../../lib/server/billing';
import { getDb } from '../../../lib/server/db';
import { payments } from '../../../lib/server/db/schema';
import { isPaynowMock } from '../../../lib/server/paynow';

export const load = async ({ locals, url }) => {
	if (!isPaynowMock()) error(404, 'Not found');
	if (!locals.user) redirect(303, '/login');

	const reference = url.searchParams.get('reference') ?? '';
	const db = await getDb();
	const payment = await db
		.select()
		.from(payments)
		.where(and(eq(payments.reference, reference), eq(payments.userId, locals.user.id)))
		.limit(1);

	if (!payment[0]) error(404, 'Payment not found');

	return {
		reference,
		plan: payment[0].plan,
		amountCents: payment[0].amountCents,
		currency: payment[0].currency,
		status: payment[0].status
	};
};

export const actions = {
	default: async ({ locals, url }) => {
		if (!isPaynowMock()) error(404, 'Not found');
		if (!locals.user) redirect(303, '/login');

		const reference = url.searchParams.get('reference') ?? '';
		const payment = await markMockPaymentPaid(locals.user.id, reference);
		if (!payment) error(404, 'Payment not found');

		redirect(303, '/billing/success');
	}
};
