<script lang="ts">
	import BottomNav from '../../lib/components/BottomNav.svelte';
	import MatchSpotlight from '../../lib/components/MatchSpotlight.svelte';
	import { demoJobs } from '../../lib/data/demo';

	const stats = [
		{ label: 'New matches', value: '12', note: '3 need a decision' },
		{ label: 'Applied', value: '4', note: 'this week' },
		{ label: 'Interviews', value: '1', note: 'Thursday, 10:00' },
		{ label: 'Docs ready', value: '7', note: '2 need review' }
	];
</script>

<svelte:head>
	<title>Dashboard - Mukana</title>
	<meta
		name="description"
		content="Your Mukana workspace: matches, applications, documents and interview preparation."
	/>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8 pb-24 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Your workspace</p>
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Good morning.
			</h1>
			<p class="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
				Three roles need a decision today. Four applications are waiting on a reply. Your next
				interview is on Thursday.
			</p>
		</div>
		<a
			href="/#pricing"
			class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
		>
			Manage plan
		</a>
	</div>

	<div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
		{#each stats as stat}
			<div class="rounded-2xl border border-line bg-surface p-4">
				<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">{stat.label}</p>
				<p class="mt-2 font-display text-2xl font-bold text-ink">{stat.value}</p>
				<p class="mt-1 text-xs text-ink-muted">{stat.note}</p>
			</div>
		{/each}
	</div>

	<div class="mt-8 flex flex-wrap items-center justify-between gap-3">
		<h2 id="matches" class="scroll-mt-24 font-display text-xl font-bold text-ink">Matches for you</h2>
		<div class="flex rounded-full border border-line bg-surface p-1 text-xs font-semibold">
			<button type="button" class="rounded-full px-3 py-1.5 text-ink-muted">Strict</button>
			<button type="button" class="rounded-full bg-brand px-3 py-1.5 text-on-brand">Balanced</button>
			<button type="button" class="rounded-full px-3 py-1.5 text-ink-muted">Broad</button>
		</div>
	</div>

	<div class="mt-4 grid gap-4 lg:grid-cols-2">
		{#each demoJobs as job}
			<MatchSpotlight {job} />
		{/each}
	</div>

	<div class="mt-8 grid gap-4 md:grid-cols-2">
		<section id="documents" class="scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Documents</h2>
			<p class="mt-1 text-sm text-ink-muted">Your latest tailored CV and cover letter.</p>
			<div class="mt-4 space-y-3">
				<div
					class="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 px-3 py-3"
				>
					<div>
						<p class="text-sm font-semibold text-ink">CV - Zambezi Digital Bank</p>
						<p class="text-xs text-ink-muted">PDF - updated 2 hours ago</p>
					</div>
					<span class="text-xs font-semibold text-match-text">Ready</span>
				</div>
				<div
					class="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 px-3 py-3"
				>
					<div>
						<p class="text-sm font-semibold text-ink">Cover letter - Acacia Learning Group</p>
						<p class="text-xs text-ink-muted">DOCX - updated yesterday</p>
					</div>
					<span class="text-xs font-semibold text-warn">Needs review</span>
				</div>
			</div>
		</section>

		<section id="prep" class="scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Interview prep</h2>
			<p class="mt-1 text-sm text-ink-muted">Next session: Zambezi Digital Bank - Thursday 10:00.</p>
			<div class="mt-4 rounded-xl bg-match-light p-4">
				<p class="text-xs font-semibold uppercase tracking-wider text-match-text">Readiness</p>
				<p class="mt-1 font-display text-3xl font-bold text-ink">72%</p>
				<div class="mt-3 h-2 rounded-full bg-surface">
					<div class="h-2 w-[72%] rounded-full bg-match"></div>
				</div>
			</div>
			<a href="/#pricing" class="mt-4 inline-flex text-sm font-semibold text-link">
				Open prep guide
			</a>
		</section>
	</div>

	<section id="profile" class="mt-8 scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
		<div class="flex flex-wrap items-start justify-between gap-4">
			<div>
				<h2 class="font-display text-lg font-bold text-ink">Profile readiness</h2>
				<p class="mt-1 text-sm text-ink-muted">
					Early-career candidate - Harare
				</p>
			</div>
			<span class="rounded-full bg-match-light px-3 py-1 text-sm font-bold text-match-text">68%</span>
		</div>
		<div class="mt-4 grid gap-3 sm:grid-cols-3">
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add freelance projects</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlocks 42 junior roles</p>
			</div>
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add driver licence</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlocks 18 field roles</p>
			</div>
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add CCTV/NVR experience</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlocks 11 technician roles</p>
			</div>
		</div>
	</section>
</div>

<BottomNav />
