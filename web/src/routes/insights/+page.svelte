<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const market = $derived(data.market);
	const maxCategory = $derived(Math.max(1, ...market.byFamily.map((row) => row.jobs)));
	const maxWeek = $derived(Math.max(1, ...market.weeklyVolume.map((row) => row.jobs)));

	function pct(value: number, max: number) {
		return `${Math.max(2, Math.round((value / max) * 100))}%`;
	}

	function number(value: number) {
		return value.toLocaleString('en-GB');
	}
</script>

<svelte:head>
	<title>Market insights - Mukana</title>
	<meta
		name="description"
		content="Zimbabwe job market snapshot: supply by role family, typical scores, remote share and posting velocity."
	/>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8 pb-24 sm:px-6">
	<div class="max-w-2xl">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Market insights</p>
		<h1 class="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
			What the market is actually hiring for.
		</h1>
		<p class="mt-3 text-sm leading-relaxed text-ink-muted">
			Aggregated from {number(market.totals.jobs)} postings collected since launch. Figures are
			descriptive, not advice - a category with few jobs is not a bad career, it is just quieter
			on the boards we read.
		</p>
	</div>

	<div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Live jobs</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(market.totals.live)}</p>
			<p class="mt-1 text-xs text-ink-muted">of {number(market.totals.jobs)} collected</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">New this week</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(market.totals.last7d)}</p>
			<p class="mt-1 text-xs text-ink-muted">{number(market.totals.last30d)} in 30 days</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Marked remote</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{market.totals.remoteShare}%</p>
			<p class="mt-1 text-xs text-ink-muted">of all postings</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">With a salary</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(market.totals.withSalary)}</p>
			<p class="mt-1 text-xs text-ink-muted">most postings hide pay</p>
		</div>
	</div>

	<section class="mt-8 rounded-2xl border border-line bg-surface p-4 sm:p-5">
		<h2 class="font-display text-lg font-bold text-ink">Supply by role family</h2>
		<p class="mt-1 text-sm text-ink-muted">
			How many current postings name each field, and the median fit score for people who list it
			as a target. A big bar with a low score means demand exists but qualification gates are
			tight.
		</p>
		<div class="mt-4 space-y-2">
			{#each market.byFamily as row}
				<div class="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
					<p class="min-w-0 truncate text-sm font-medium text-ink">{row.family}</p>
					<p class="text-right text-xs font-semibold text-ink-muted">
						{number(row.jobs)} Â· {row.share}%
						{#if row.medianScore !== null}
							<span class="ml-1 text-match-text">Â· {row.medianScore} fit</span>
						{/if}
					</p>
					<div class="col-span-2 h-2 rounded-full bg-surface-2">
						<div class="h-2 rounded-full bg-brand" style={`width: ${pct(row.jobs, maxCategory)}`}></div>
					</div>
				</div>
			{/each}
		</div>
	</section>

	<div class="mt-4 grid gap-4 md:grid-cols-2">
		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">Where the jobs come from</h2>
			<p class="mt-1 text-sm text-ink-muted">Sources we read, and how fresh each one is.</p>
			<div class="mt-4 divide-y divide-line">
				{#each market.bySource as source}
					<div class="flex items-center justify-between gap-3 py-2">
						<div class="min-w-0">
							<p class="truncate text-sm font-semibold text-ink">{source.source}</p>
							<p class="text-xs text-ink-muted">{number(source.live)} live</p>
						</div>
						<div class="shrink-0 text-right">
							<p class="text-sm font-semibold text-ink">{number(source.jobs)}</p>
							<p class="text-xs text-ink-muted">{number(source.last7d)} new</p>
						</div>
					</div>
				{/each}
			</div>
		</section>

		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">Contract type</h2>
			<p class="mt-1 text-sm text-ink-muted">
				Normalised from how each board words it - boards are inconsistent, so this is a
				best-effort grouping.
			</p>
			<ul class="mt-4 space-y-2">
				{#each market.byType as row}
					<li class="flex items-center justify-between gap-3 text-sm">
						<span class="min-w-0 truncate text-ink">{row.label}</span>
						<span class="shrink-0 font-semibold text-ink-muted">{number(row.jobs)}</span>
					</li>
				{/each}
			</ul>
		</section>
	</div>

	<section class="mt-4 min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
		<h2 class="font-display text-lg font-bold text-ink">Posting volume by week</h2>
		<p class="mt-1 text-sm text-ink-muted">
			How many new postings we saw each week over the last 12 weeks.
		</p>
		<div class="mt-4 flex h-40 items-end gap-1.5">
			{#each market.weeklyVolume as row}
				<div class="group flex min-w-0 flex-1 flex-col items-center justify-end gap-1">
					<span class="text-[10px] font-semibold text-ink-muted opacity-0 transition-opacity group-hover:opacity-100">
						{row.jobs}
					</span>
					<div
						class="w-full rounded-t bg-match"
						style={`height: ${Math.max(3, Math.round((row.jobs / maxWeek) * 100))}%`}
						title={`${row.week}: ${row.jobs} postings`}
					></div>
				</div>
			{/each}
		</div>
		<div class="mt-2 flex justify-between text-[10px] text-ink-muted">
			<span>{market.weeklyVolume[0]?.week ?? ''}</span>
			<span>{market.weeklyVolume[market.weeklyVolume.length - 1]?.week ?? ''}</span>
		</div>
	</section>

	<div class="mt-4 grid gap-4 md:grid-cols-2">
		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">Hiring most often</h2>
			<p class="mt-1 text-sm text-ink-muted">Employers with the most postings in our data.</p>
			<ol class="mt-4 space-y-2">
				{#each market.topCompanies as company, index}
					<li class="flex items-center gap-3 text-sm">
						<span class="w-5 shrink-0 text-xs font-bold text-ink-muted">{index + 1}</span>
						<span class="min-w-0 flex-1 truncate text-ink">{company.company}</span>
						<span class="shrink-0 font-semibold text-ink-muted">{company.jobs}</span>
					</li>
				{/each}
			</ol>
		</section>

		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">How long a posting lasts</h2>
			<div class="mt-4 grid gap-3 sm:grid-cols-2">
				<div class="rounded-xl bg-surface-2 p-4">
					<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Median age</p>
					<p class="mt-1 font-display text-2xl font-bold text-ink">
						{market.freshness.medianDaysListed ?? '-'}
						<span class="text-sm font-semibold text-ink-muted">days</span>
					</p>
					<p class="mt-1 text-xs text-ink-muted">since we first saw it</p>
				</div>
				<div class="rounded-xl bg-surface-2 p-4">
					<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Time to apply</p>
					<p class="mt-1 font-display text-2xl font-bold text-ink">
						{market.freshness.medianDaysToExpiry ?? '-'}
						<span class="text-sm font-semibold text-ink-muted">days</span>
					</p>
					<p class="mt-1 text-xs text-ink-muted">between posting and deadline</p>
				</div>
			</div>
			<p class="mt-4 rounded-xl bg-warn/10 px-3 py-2 text-xs leading-relaxed text-warn">
				{number(market.totals.expired)} postings in this dataset have already closed. Closed
				roles stay in the counts above, so treat historical categories as a rough guide.
			</p>
		</section>
	</div>
</div>
