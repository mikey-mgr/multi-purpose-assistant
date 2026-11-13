<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const analytics = $derived(data.analytics);
	const maxBand = $derived(Math.max(1, ...analytics.scoreBands.map((row) => row.matches)));
	const maxWeek = $derived(Math.max(1, ...analytics.weeklyMatches.map((row) => row.matches)));

	function number(value: number) {
		return value.toLocaleString('en-GB');
	}
</script>

<svelte:head>
	<title>Pipeline diagnostics - Mukana</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8 pb-24 sm:px-6">
	<div class="max-w-2xl">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Internal</p>
		<h1 class="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
			Pipeline diagnostics.
		</h1>
		<p class="mt-3 text-sm leading-relaxed text-ink-muted">
			Where applications actually get through, and where the matcher is mis-calibrated. Not shown
			to other users.
		</p>
	</div>

	<div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Matches</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(analytics.totals.matches)}</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Applied</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(analytics.totals.applied)}</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Documents</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(analytics.totals.documents)}</p>
		</div>
		<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Kits</p>
			<p class="mt-2 font-display text-2xl font-bold text-ink">{number(analytics.totals.kits)}</p>
		</div>
	</div>

	<section class="mt-8 min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
		<h2 class="font-display text-lg font-bold text-ink">Funnel by source</h2>
		<p class="mt-1 text-sm text-ink-muted">
			Applied rate = applications sent divided by matches created. A source that produces many
			matches but few applications is not paying for itself.
		</p>
		<div class="mt-4 -mx-2 overflow-x-auto">
			<table class="w-full min-w-[34rem] text-sm">
				<thead>
					<tr class="text-left text-xs uppercase tracking-wider text-ink-muted">
						<th class="px-2 py-2 font-semibold">Source</th>
						<th class="px-2 py-2 text-right font-semibold">Matches</th>
						<th class="px-2 py-2 text-right font-semibold">Matched</th>
						<th class="px-2 py-2 text-right font-semibold">Generated</th>
						<th class="px-2 py-2 text-right font-semibold">Applied</th>
						<th class="px-2 py-2 text-right font-semibold">Rejected</th>
						<th class="px-2 py-2 text-right font-semibold">Applied %</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line">
					{#each analytics.funnel as row}
						<tr>
							<td class="px-2 py-2 font-medium text-ink">{row.source}</td>
							<td class="px-2 py-2 text-right text-ink-muted">{number(row.matches)}</td>
							<td class="px-2 py-2 text-right text-ink-muted">{number(row.matched)}</td>
							<td class="px-2 py-2 text-right text-ink-muted">{number(row.generated)}</td>
							<td class="px-2 py-2 text-right font-semibold text-match-text">
								{number(row.applied)}
							</td>
							<td class="px-2 py-2 text-right text-ink-muted">{number(row.rejected)}</td>
							<td class="px-2 py-2 text-right font-semibold text-ink">{row.appliedRate}%</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	<div class="mt-4 grid gap-4 md:grid-cols-2">
		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">Score distribution</h2>
			<p class="mt-1 text-sm text-ink-muted">
				A healthy matcher uses the middle of the scale. Everything bunched at one end means the
				prompt is too loose or too strict.
			</p>
			<div class="mt-4 space-y-2">
				{#each analytics.scoreBands as band}
					<div class="grid grid-cols-[4.5rem_1fr_auto] items-center gap-3">
						<span class="text-xs font-semibold text-ink-muted">{band.band}</span>
						<div class="h-2 rounded-full bg-surface-2">
							<div
								class="h-2 rounded-full bg-match"
								style={`width: ${Math.max(2, Math.round((band.matches / maxBand) * 100))}%`}
							></div>
						</div>
						<span class="text-xs font-semibold text-ink">{number(band.matches)}</span>
					</div>
				{/each}
			</div>
		</section>

		<section class="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
			<h2 class="font-display text-lg font-bold text-ink">Documents produced</h2>
			<ul class="mt-4 space-y-2">
				{#each analytics.documents as row}
					<li class="flex items-center justify-between gap-3 text-sm">
						<span class="text-ink">{row.type}</span>
						<span class="font-semibold text-ink-muted">{number(row.count)}</span>
					</li>
				{/each}
			</ul>
		</section>
	</div>

	<section class="mt-4 min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5">
		<h2 class="font-display text-lg font-bold text-ink">Matches per week</h2>
		<div class="mt-4 flex h-40 items-end gap-1.5">
			{#each analytics.weeklyMatches as row}
				<div class="group flex min-w-0 flex-1 flex-col items-center justify-end gap-1">
					<span class="text-[10px] font-semibold text-ink-muted opacity-0 transition-opacity group-hover:opacity-100">
						{row.matches}
					</span>
					<div class="flex w-full flex-col justify-end" style={`height: ${Math.max(3, Math.round((row.matches / maxWeek) * 100))}%`}>
						<div class="w-full rounded-t bg-brand/40" style={`height: ${row.matches ? Math.max(8, Math.round((row.applied / row.matches) * 100)) : 0}%`}></div>
						<div class="w-full bg-brand" style={`height: ${row.matches ? Math.max(0, 100 - Math.round((row.applied / row.matches) * 100)) : 0}%`}></div>
					</div>
				</div>
			{/each}
		</div>
		<p class="mt-2 text-xs text-ink-muted">
			Solid = matches created, lighter band = the share that converted to applications.
		</p>
	</section>
</div>
