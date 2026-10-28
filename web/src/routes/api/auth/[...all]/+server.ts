import type { RequestHandler } from './$types';
import { getAuth } from '../../../../lib/server/auth';

const handler: RequestHandler = async ({ request }) => {
	const auth = await getAuth();
	return auth.handler(request);
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
