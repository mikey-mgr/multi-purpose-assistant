<script lang="ts">
	import { inlineHtml } from '../markdown';

	type Cv = {
		name?: string;
		headline?: string;
		location?: string;
		email?: string;
		phone?: string;
		custom_connections?: Array<{ placeholder?: string; url?: string }>;
		sections?: Record<string, any[]>;
	};

	let { cv }: { cv: Cv } = $props();

	const sections = $derived(Object.entries(cv.sections ?? {}));
	const summaryNames = new Set(['PROFESSIONAL PROFILE', 'SUMMARY', 'PROFILE']);
	const skillNames = new Set(['TECHNICAL SKILLS', 'SKILLS']);

	function formatDate(value: unknown): string {
		if (typeof value !== 'string' || !value) return '';
		const [year, month] = value.split('-');
		if (!year) return value;
		if (!month) return year;
		const date = new Date(Number(year), Number(month) - 1, 1);
		return Number.isNaN(date.getTime())
			? value
			: date.toLocaleDateString('en', { month: 'short', year: 'numeric' });
	}

	function dateRange(item: Record<string, unknown>): string {
		const start = formatDate(item.start_date);
		const end = item.end_date ? formatDate(item.end_date) : 'Present';
		return start ? `${start} - ${end}` : '';
	}

	function titleFor(item: Record<string, unknown>): string {
		if (item.position || item.company) {
			return [item.position, item.company].filter(Boolean).join(' at ');
		}
		if (item.institution) {
			return [item.degree, item.area].filter(Boolean).join(', ') + ` - ${item.institution}`;
		}
		if (item.name && item.issuer) return `${item.name} - ${item.issuer}`;
		return String(item.name ?? item.label ?? '');
	}
</script>

<article class="rounded-2xl border border-line bg-surface p-6 text-ink shadow-sm sm:p-10">
	<header class="border-b border-line pb-5">
		<h1 class="font-display text-3xl font-bold tracking-tight">{cv.name ?? 'Candidate'}</h1>
		{#if cv.headline}
			<p class="mt-1 text-sm font-medium text-ink-muted">{cv.headline}</p>
		{/if}
		<div class="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
			{#if cv.location}<span>{cv.location}</span>{/if}
			{#if cv.email}<a href={`mailto:${cv.email}`} class="hover:text-ink">{cv.email}</a>{/if}
			{#if cv.phone}<span>{cv.phone}</span>{/if}
			{#each cv.custom_connections ?? [] as link}
				{#if link.url}
					<a href={link.url} target="_blank" rel="noreferrer" class="font-medium hover:text-ink">
						{link.placeholder ?? 'Link'}
					</a>
				{/if}
			{/each}
		</div>
	</header>

	<div class="mt-6 space-y-6">
		{#each sections as [heading, items]}
			<section>
				<h2 class="border-b border-line pb-1 text-xs font-bold uppercase tracking-[0.16em] text-ink-muted">
					{heading}
				</h2>
				<div class="mt-3 space-y-3">
					{#if skillNames.has(heading)}
						{#each items as item}
							{#if typeof item === 'object' && item}
								<p class="text-sm leading-relaxed">
									<strong>{item.label}:</strong>
									{item.details}
								</p>
							{:else}
								<p class="text-sm leading-relaxed">{item}</p>
							{/if}
						{/each}
					{:else if summaryNames.has(heading)}
						{#each items as item}
							<p class="text-sm leading-relaxed text-ink">
								{@html inlineHtml(String(item))}
							</p>
						{/each}
					{:else}
						{#each items as item}
							{#if typeof item === 'string'}
								<p class="text-sm leading-relaxed text-ink">{@html inlineHtml(item)}</p>
							{:else if item && typeof item === 'object'}
								<div>
									<div class="flex flex-wrap items-baseline justify-between gap-2">
										<h3 class="text-sm font-semibold text-ink">
											{@html inlineHtml(titleFor(item))}
										</h3>
										{#if dateRange(item)}
											<span class="text-xs text-ink-muted">{dateRange(item)}</span>
										{/if}
									</div>
									{#if item.location}
										<p class="mt-0.5 text-xs text-ink-muted">{item.location}</p>
									{/if}
									{#if item.highlights}
										<ul class="mt-1.5 list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink">
											{#each item.highlights as highlight}
												<li>{@html inlineHtml(String(highlight))}</li>
											{/each}
										</ul>
									{/if}
								</div>
							{/if}
						{/each}
					{/if}
				</div>
			</section>
		{/each}
	</div>
</article>
