<script lang="ts">
	import BottomNav from '../../lib/components/BottomNav.svelte';
	import MatchSpotlight from '../../lib/components/MatchSpotlight.svelte';
	import { demoJobs } from '../../lib/data/demo';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const jobsToShow = $derived(data.matches.length ? data.matches : demoJobs);

	const stats = $derived([
		{ label: 'New matches', value: String(data.stats.newMatches), note: 'waiting for a decision' },
		{ label: 'Applied', value: String(data.stats.applied), note: 'total sent' },
		{ label: 'Matches', value: String(data.stats.totalMatches), note: 'all time' },
		{ label: 'Documents', value: String(data.stats.documents), note: 'tailored files' }
	]);

	const docs = $derived(
		data.documents.length
			? data.documents
			: [
					{
						id: 'sample-resume',
						type: 'resume',
						jobTitle: 'Zambezi Digital Bank',
						company: null,
						promptName: null,
						createdAt: null
					},
					{
						id: 'sample-cover',
						type: 'cover_letter',
						jobTitle: 'Acacia Learning Group',
						company: null,
						promptName: null,
						createdAt: null
					}
				]
	);

	function docLabel(type: string) {
		if (type === 'resume') return 'CV';
		if (type === 'cover_letter') return 'Cover letter';
		if (type === 'interview_prep') return 'Interview prep';
		return type;
	}
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
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">Good morning.</h1>
			<p class="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
				{data.stats.newMatches > 0
					? `${data.stats.newMatches} new matches need a decision. ${data.stats.applied} applications are on record.`
					: 'Your workspace is ready. New matches will appear after the next scrape.'}
			</p>
		</div>
		<a
			href="/#pricing"
			class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
		>
			Manage plan
		</a>
	</div>

	{#if data.preview}
		<div class="mt-6 rounded-xl border border-line bg-match-light px-4 py-3 text-sm text-match-text">
			Showing sample matches until your first scrape finishes. Real matches appear here automatically.
		</div>
	{/if}

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
		<div class="flex items-center gap-3">
			<h2 id="matches" class="scroll-mt-24 font-display text-xl font-bold text-ink">
				Matches for you
			</h2>
			<a href="/matches" class="text-xs font-semibold text-link">View all</a>
		</div>
		<div class="flex rounded-full border border-line bg-surface p-1 text-xs font-semibold">
			<button type="button" class="rounded-full px-3 py-1.5 text-ink-muted">Strict</button>
			<button type="button" class="rounded-full bg-brand px-3 py-1.5 text-on-brand">Balanced</button>
			<button type="button" class="rounded-full px-3 py-1.5 text-ink-muted">Broad</button>
		</div>
	</div>

	<div class="mt-4 grid gap-4 lg:grid-cols-2">
		{#each jobsToShow as job}
			<MatchSpotlight {job} />
		{/each}
	</div>

	<div class="mt-8 grid gap-4 md:grid-cols-2">
		<section id="documents" class="scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Documents</h2>
			<p class="mt-1 text-sm text-ink-muted">Your latest tailored files.</p>
			<div class="mt-4 space-y-3">
				{#each docs as document}
					<div
						class="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 px-3 py-3"
					>
						<div class="min-w-0">
							<p class="truncate text-sm font-semibold text-ink">
								{docLabel(document.type)} - {document.jobTitle ?? 'General'}
							</p>
							<p class="truncate text-xs text-ink-muted">
								{document.company ?? 'Tailored document'}
							</p>
						</div>
						<span class="shrink-0 text-xs font-semibold text-match-text">Ready</span>
					</div>
				{/each}
			</div>
		</section>

		<section id="prep" class="scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
			<h2 class="font-display text-lg font-bold text-ink">Interview prep</h2>
			<p class="mt-1 text-sm text-ink-muted">
				{data.preview ? 'Sample session: Zambezi Digital Bank - Thursday 10:00.' : 'No interview scheduled yet.'}
			</p>
			<div class="mt-4 rounded-xl bg-match-light p-4">
				<p class="text-xs font-semibold uppercase tracking-wider text-match-text">Profile readiness</p>
				<p class="mt-1 font-display text-3xl font-bold text-ink">{data.profile.readiness}%</p>
				<div class="mt-3 h-2 rounded-full bg-surface">
					<div
						class="h-2 rounded-full bg-match"
						style={`width: ${Math.max(0, Math.min(100, data.profile.readiness))}%`}
					></div>
				</div>
			</div>
			<a href="/onboarding" class="mt-4 inline-flex text-sm font-semibold text-link">
				Complete your profile
			</a>
		</section>
	</div>

	<section id="profile" class="mt-8 scroll-mt-24 rounded-2xl border border-line bg-surface p-5">
		<div class="flex flex-wrap items-start justify-between gap-4">
			<div>
				<h2 class="font-display text-lg font-bold text-ink">Profile readiness</h2>
				<p class="mt-1 text-sm text-ink-muted">
					{data.profile.headline ?? 'Add a headline and target roles'}
					{data.profile.location ? ` - ${data.profile.location}` : ''}
				</p>
			</div>
			<span class="rounded-full bg-match-light px-3 py-1 text-sm font-bold text-match-text">
				{data.profile.readiness}%
			</span>
		</div>
		<div class="mt-4 grid gap-3 sm:grid-cols-3">
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add freelance projects</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock more junior roles</p>
			</div>
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add driver licence</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock field roles</p>
			</div>
			<div class="rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add CCTV/NVR experience</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock technician roles</p>
			</div>
		</div>
	</section>
</div>

<BottomNav />
