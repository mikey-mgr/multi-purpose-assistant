const SOURCE_NAMES = [
	/vacancymail/gi,
	/vacancybox/gi,
	/ihararejobs?/gi,
	/applynow/gi,
	/whatsapp/gi
];

const BOILERPLATE = [
	/\bCV Writing Services\b/gi,
	/Click to Apply\s*\/\s*View More Information/gi
];

export function publicSummary(value: string | null | undefined, max = 320): string {
	let text = (value ?? '').replace(/https?:\/\/\S+/gi, ' ').replace(/www\.\S+/gi, ' ');
	for (const pattern of SOURCE_NAMES) text = text.replace(pattern, ' ');
	for (const pattern of BOILERPLATE) text = text.replace(pattern, ' ');
	return text.replace(/\s+/g, ' ').trim().slice(0, max);
}
