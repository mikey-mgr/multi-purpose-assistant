const EMAIL_PATTERN = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const GENERAL_MAILBOXES = new Set([
	'jobs',
	'careers',
	'hr',
	'recruitment',
	'recruiting',
	'applications',
	'apply',
	'info',
	'admin',
	'office'
]);

export function emailsFrom(text: string): string[] {
	const found = new Set<string>();
	for (const match of text.matchAll(EMAIL_PATTERN)) {
		found.add(match[0].toLowerCase());
	}
	return [...found];
}

function tokens(value: string): string[] {
	return value.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

export function chooseRecipient(emails: string[], context: string): string | null {
	if (emails.length <= 1) return emails[0] ?? null;
	const keywords = new Set(tokens(context).filter((token) => token.length >= 4));

	let best: string | null = null;
	let bestScore = 0;
	let tied = false;
	for (const email of emails) {
		const parts = new Set(tokens(email.split('@')[0]));
		let score = 0;
		for (const keyword of keywords) {
			if (parts.has(keyword)) score += 2;
		}
		if (score > bestScore) {
			best = email;
			bestScore = score;
			tied = false;
		} else if (score === bestScore && score > 0) {
			tied = true;
		}
	}
	if (bestScore > 0 && !tied) return best;

	const general = emails.filter((email) => GENERAL_MAILBOXES.has(email.split('@')[0]));
	return general.length === 1 ? general[0] : null;
}
