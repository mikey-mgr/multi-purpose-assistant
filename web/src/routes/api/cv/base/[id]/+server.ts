import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getBaseCvFile } from '../../../../../lib/server/resume/base-cv';

export const GET: RequestHandler = async (event) => {
	if (!event.locals.user) {
		error(401, 'Unauthorized');
	}

	const file = await getBaseCvFile({
		userId: event.locals.user.id,
		documentId: event.params.id
	});
	if (!file) error(404, 'CV not found');

	return new Response(file.bytes, {
		headers: {
			'Content-Type': 'application/pdf',
			'Content-Disposition': `attachment; filename="${file.filename}"`,
			'Cache-Control': 'private, no-store'
		}
	});
};
