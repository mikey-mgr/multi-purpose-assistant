import { PDFDocument, StandardFonts, rgb } from 'pdf-lib';

const PAGE_WIDTH = 595.28;
const PAGE_HEIGHT = 841.89;
const MARGIN = 48;
const MAX_WIDTH = PAGE_WIDTH - MARGIN * 2;

type PdfProfile = {
	name: string;
	email?: string | null;
	phone?: string | null;
	location?: string | null;
	headline?: string | null;
	resumeText: string;
	jobTitle: string;
};

function clean(value: string): string {
	return value
		.replace(/[\u2018\u2019]/g, "'")
		.replace(/[\u201c\u201d]/g, '"')
		.replace(/[\u2013\u2014]/g, '-')
		.replace(/[\u2022]/g, '-')
		.replace(/\u00a0/g, ' ')
		.replace(/[^\x09\x0a\x0d\x20-\x7e]/g, '');
}

function wrap(text: string, font: { widthOfTextAtSize: (text: string, size: number) => number }, size: number, maxWidth = MAX_WIDTH): string[] {
	const words = clean(text).split(/\s+/).filter(Boolean);
	const lines: string[] = [];
	let line = '';
	for (const word of words) {
		const candidate = line ? `${line} ${word}` : word;
		if (font.widthOfTextAtSize(candidate, size) > maxWidth && line) {
			lines.push(line);
			line = word;
		} else {
			line = candidate;
		}
	}
	if (line) lines.push(line);
	return lines.length ? lines : [''];
}

export async function buildResumePdf(profile: PdfProfile): Promise<Uint8Array> {
	const doc = await PDFDocument.create();
	const regular = await doc.embedFont(StandardFonts.Helvetica);
	const bold = await doc.embedFont(StandardFonts.HelveticaBold);
	let page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
	let y = PAGE_HEIGHT - MARGIN;

	function nextPage() {
		page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
		y = PAGE_HEIGHT - MARGIN;
	}

	function ensure(height: number) {
		if (y - height < MARGIN) nextPage();
	}

	function text(value: string, size: number, font = regular, color = rgb(0.1, 0.1, 0.1), gap = 5) {
		for (const line of wrap(value, font, size)) {
			ensure(size + gap);
			page.drawText(line, { x: MARGIN, y, size, font, color });
			y -= size + gap;
		}
	}

	text(profile.name, 22, bold);
	if (profile.headline) text(profile.headline, 10, regular, rgb(0.35, 0.35, 0.35), 3);
	const contact = [profile.location, profile.email, profile.phone].filter(Boolean).join('  |  ');
	if (contact) text(contact, 9, regular, rgb(0.3, 0.3, 0.3), 10);
	page.drawLine({
		start: { x: MARGIN, y },
		end: { x: PAGE_WIDTH - MARGIN, y },
		thickness: 0.8,
		color: rgb(0.8, 0.8, 0.8)
	});
	y -= 16;

	const lines = clean(profile.resumeText).split('\n');
	const headings = new Set([
		'PROFESSIONAL SUMMARY',
		'PROFESSIONAL PROFILE',
		'SUMMARY',
		'SKILLS',
		'TECHNICAL SKILLS',
		'EXPERIENCE',
		'WORK EXPERIENCE',
		'EDUCATION',
		'PROJECTS',
		'CERTIFICATIONS',
		'REFERENCES'
	]);
	for (const raw of lines) {
		const line = raw.trim();
		if (!line) {
			y -= 3;
			continue;
		}
		const heading = headings.has(line.toUpperCase()) || (line.length < 42 && /^[A-Z][A-Z &/-]+$/.test(line));
		if (heading) {
			ensure(22);
			y -= 4;
			text(line.toUpperCase(), 10, bold, rgb(0.12, 0.12, 0.12), 4);
		} else if (/^[-*•]\s+/.test(line)) {
			text(`- ${line.replace(/^[-*•]\s+/, '')}`, 9.5, regular, rgb(0.2, 0.2, 0.2), 3);
		} else {
			text(line, 9.5, regular, rgb(0.2, 0.2, 0.2), 3);
		}
	}

	return doc.save();
}

export async function mergePdfs(documents: Uint8Array[]): Promise<Uint8Array> {
	const merged = await PDFDocument.create();
	for (const bytes of documents) {
		const source = await PDFDocument.load(bytes);
		const pages = await merged.copyPages(source, source.getPageIndices());
		for (const page of pages) merged.addPage(page);
	}
	return merged.save();
}

export async function buildCoverLetterPdf(input: {
	name: string;
	email?: string | null;
	phone?: string | null;
	location?: string | null;
	body: string;
	jobTitle: string;
	company?: string | null;
}): Promise<Uint8Array> {
	const doc = await PDFDocument.create();
	const regular = await doc.embedFont(StandardFonts.Helvetica);
	const bold = await doc.embedFont(StandardFonts.HelveticaBold);
	let page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
	let y = PAGE_HEIGHT - MARGIN;

	function nextPage() {
		page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
		y = PAGE_HEIGHT - MARGIN;
	}

	function ensure(height: number) {
		if (y - height < MARGIN) nextPage();
	}

	function paragraph(value: string, size = 10.5, font = regular, gap = 6) {
		for (const line of wrap(value, font, size)) {
			ensure(size + gap);
			page.drawText(line, { x: MARGIN, y, size, font, color: rgb(0.15, 0.15, 0.15) });
			y -= size + gap;
		}
		y -= 8;
	}

	paragraph(input.name, 16, bold, 4);
	paragraph([input.location, input.email, input.phone].filter(Boolean).join('  |  '), 9, regular, 3);
	y -= 12;
	paragraph(`Re: ${input.jobTitle}${input.company ? ` at ${input.company}` : ''}`, 11, bold, 4);
	for (const block of input.body.split(/\n{2,}/)) {
		paragraph(block.replace(/\n/g, ' '), 10.5, regular);
	}
	return doc.save();
}
