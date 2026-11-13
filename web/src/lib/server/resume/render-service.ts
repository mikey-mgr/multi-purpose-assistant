import { envValue } from '../env';
import type { CvTemplate } from './types';

export type RenderAttachment = {
	name: string;
	mime: string;
	contentBase64: string;
};

export type RenderResult = {
	cvPdf: string;
	coverLetterPdf: string | null;
	coverLetterDocx: string | null;
	mergedPdf: string | null;
	cvPages: number;
	mergedPages: number | null;
};

type RenderResponse = {
	cv_pdf: string;
	cover_letter_pdf: string | null;
	cover_letter_docx: string | null;
	merged_pdf: string | null;
	cv_pages: number;
	merged_pages: number | null;
};

export async function renderApplication(input: {
	cv: unknown;
	theme: CvTemplate;
	coverLetter: string | null;
	attachments: RenderAttachment[];
	merge: boolean;
}): Promise<{ result: RenderResult | null; error?: string }> {
	const base = envValue('RENDER_SERVICE_URL');
	const secret = envValue('RENDER_SERVICE_SECRET');
	if (!base || !secret) {
		return { result: null, error: 'Renderer is not configured' };
	}

	try {
		const response = await fetch(`${base.replace(/\/$/, '')}/render`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-render-secret': secret
			},
			body: JSON.stringify({
				theme: input.theme,
				cv: input.cv,
				cover_letter: input.coverLetter,
				attachments: input.attachments.map((attachment) => ({
					name: attachment.name,
					mime: attachment.mime,
					content_base64: attachment.contentBase64
				})),
				merge: input.merge
			}),
			signal: AbortSignal.timeout(180000)
		});
		if (!response.ok) {
			const detail = (await response.text()).slice(0, 600);
			console.error('Renderer failed', response.status, detail);
			return { result: null, error: `Renderer returned ${response.status}: ${detail}` };
		}
		const payload = (await response.json()) as RenderResponse;
		return {
			result: {
				cvPdf: payload.cv_pdf,
				coverLetterPdf: payload.cover_letter_pdf,
				coverLetterDocx: payload.cover_letter_docx,
				mergedPdf: payload.merged_pdf,
				cvPages: payload.cv_pages,
				mergedPages: payload.merged_pages
			}
		};
	} catch (error) {
		console.error('Renderer request failed', error);
		return {
			result: null,
			error: `Renderer request failed: ${error instanceof Error ? error.message : String(error)}`
		};
	}
}
