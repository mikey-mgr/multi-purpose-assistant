function escapeHtml(value: string): string {
	return value
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

function safeUrl(value: string): string {
	try {
		const url = new URL(value);
		return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : '#';
	} catch {
		return '#';
	}
}

export function inlineHtml(value: string): string {
	let text = escapeHtml(value);
	text = text.replace(
		/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
		(_match, label: string, url: string) =>
			`<a href="${escapeHtml(safeUrl(url))}" target="_blank" rel="noreferrer">${label}</a>`
	);
	text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
	text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
	return text;
}

export function renderMarkdown(source: string): string {
	const lines = (source ?? '').replace(/\r\n/g, '\n').split('\n');
	const output: string[] = [];
	let listType: 'ul' | 'ol' | null = null;

	function closeList() {
		if (listType) {
			output.push(`</${listType}>`);
			listType = null;
		}
	}

	for (const raw of lines) {
		const line = raw.trimEnd();
		if (!line.trim()) {
			closeList();
			continue;
		}
		const heading = line.match(/^(#{1,4})\s+(.*)$/);
		if (heading) {
			closeList();
			const level = Math.min(4, heading[1].length);
			output.push(`<h${level}>${inlineHtml(heading[2])}</h${level}>`);
			continue;
		}
		const bullet = line.match(/^\s*[-*]\s+(.*)$/);
		if (bullet) {
			if (listType !== 'ul') {
				closeList();
				output.push('<ul>');
				listType = 'ul';
			}
			output.push(`<li>${inlineHtml(bullet[1])}</li>`);
			continue;
		}
		const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
		if (numbered) {
			if (listType !== 'ol') {
				closeList();
				output.push('<ol>');
				listType = 'ol';
			}
			output.push(`<li>${inlineHtml(numbered[1])}</li>`);
			continue;
		}
		closeList();
		output.push(`<p>${inlineHtml(line)}</p>`);
	}
	closeList();
	return output.join('\n');
}
