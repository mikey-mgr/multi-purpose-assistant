type Contact = {
	name: string;
	email: string;
	phone: string | null;
};

function digits(value: string): string {
	return value.replace(/\D+/g, '');
}

export function normalizeCoverLetter(text: string, contact: Contact): string {
	let cleaned = text
		.replace(/\r/g, '')
		.replace(/\u2013/g, '-')
		.replace(/\u2014/g, '-')
		.replace(/\u2018|\u2019/g, "'")
		.replace(/\u201c|\u201d/g, '"')
		.trim();

	const lines = cleaned.split('\n');
	const dearIndex = lines.findIndex((line) => /^\s*dear\b/i.test(line));
	if (dearIndex > 0) {
		cleaned = lines.slice(dearIndex).join('\n').trim();
	}

	const contactEmail = contact.email.toLowerCase();
	const contactPhone = contact.phone ? digits(contact.phone) : '';
	const emailPattern = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
	const phonePattern = /(?:\+?\d[\d\s()-]{7,}\d)/g;

	cleaned = cleaned
		.split('\n')
		.filter((line) => {
			const emails = line.match(emailPattern) ?? [];
			if (emails.some((email) => email.toLowerCase() !== contactEmail)) return false;
			const phones = line.match(phonePattern) ?? [];
			if (
				contactPhone &&
				phones.some((phone) => {
					const value = digits(phone);
					return value.length >= 9 && value !== contactPhone;
				})
			) {
				return false;
			}
			return true;
		})
		.join('\n')
		.trim();

	const tail = cleaned.slice(-400);
	const hasSignoff = /\b(regards|sincerely|yours faithfully|yours sincerely)\b/i.test(tail);
	if (!hasSignoff) {
		cleaned += `\n\nRegards,\n${contact.name}`;
		if (contact.phone) cleaned += `\n${contact.phone}`;
	} else {
		if (!tail.includes(contact.name)) cleaned += `\n${contact.name}`;
		if (contact.phone && !tail.includes(contact.phone)) cleaned += `\n${contact.phone}`;
	}

	return cleaned.trim();
}
