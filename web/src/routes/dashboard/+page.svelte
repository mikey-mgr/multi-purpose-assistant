<script lang="ts">
	import { onMount } from 'svelte';
	import MatchSpotlight from '../../lib/components/MatchSpotlight.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let matchMode = $state<'strict' | 'balanced' | 'broad'>('balanced');
	let savingMode = $state(false);
	let modeError = $state('');

	$effect(() => {
		matchMode = (data.profile.matchMode as 'strict' | 'balanced' | 'broad') ?? 'balanced';
	});

	async function setMatchMode(mode: 'strict' | 'balanced' | 'broad') {
		if (mode === matchMode || savingMode) return;
		savingMode = true;
		modeError = '';
		const response = await fetch('/api/profile', {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ matchMode: mode })
		});
		savingMode = false;
		if (!response.ok) {
			modeError = 'Could not update the matching mode.';
			return;
		}
		matchMode = mode;
	}

	const jobsToShow = $derived(data.matches);
	let showPilot = $state(false);
	let pilotPhone = $state('');
	let pilotBusy = $state(false);
	let pilotError = $state('');

	async function joinPilot(event: SubmitEvent) {
		event.preventDefault();
		pilotBusy = true;
		pilotError = '';
		const response = await fetch('/api/whatsapp/pilot', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ phone: pilotPhone })
		});
		const result = (await response.json().catch(() => ({}))) as { error?: string };
		pilotBusy = false;
		if (!response.ok) {
			pilotError = result.error ?? 'Could not join the pilot';
			return;
		}
		showPilot = false;
	}

	async function dismissPilot() {
		showPilot = false;
		await fetch('/api/whatsapp/pilot/dismiss', { method: 'POST' });
	}

	let greeting = $state('Hello');

	onMount(() => {
		const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
		const hour = Number(
			new Intl.DateTimeFormat('en-GB', {
				hour: 'numeric',
				hour12: false,
				timeZone
			}).format(new Date())
		) % 24;
		const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
		const firstName = data.user?.name?.trim().split(/\s+/)[0];
		greeting = `Good ${part}${firstName ? `, ${firstName}` : ''}.`;
		showPilot =
			!data.pilot.joined && data.pilot.slotsOpen > 0 && !data.pilot.promptDismissed;
	});

	const stats = $derived([
		{ label: 'Needs review', value: String(data.stats.newMatches), note: 'matches and drafts' },
		{ label: 'Applied', value: String(data.stats.applied), note: 'total sent' },
		{ label: 'Matches', value: String(data.stats.totalMatches), note: 'all time' },
		{ label: 'Documents', value: String(data.stats.documents), note: 'tailored files' }
	]);

	const docs = $derived(data.documents);

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
			<h1 class="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">{greeting}</h1>
			<p class="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
				{data.stats.newMatches > 0
					? `${data.stats.newMatches} match${data.stats.newMatches === 1 ? '' : 'es'} ready for review. ${data.stats.applied} applications are on record.`
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
		<div class="mt-6 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink-muted">
			No active matches yet. The scheduler will add them after the next scrape and matching pass.
		</div>
	{/if}

	<div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
		{#each stats as stat}
			<div class="min-w-0 rounded-2xl border border-line bg-surface p-4">
				<p class="text-xs font-semibold uppercase tracking-wider text-ink-muted">{stat.label}</p>
				<p class="mt-2 font-display text-2xl font-bold text-ink">{stat.value}</p>
				<p class="mt-1 text-xs text-ink-muted">{stat.note}</p>
			</div>
		{/each}
	</div>

	<div class="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
		<div class="min-w-0">
			<h2 id="matches" class="scroll-mt-24 font-display text-xl font-bold text-ink">
				Matches for you
			</h2>
			<div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
				<a href="/matches" class="text-xs font-semibold text-link">View all</a>
				<a href="/matches?status=rejected" class="text-xs font-semibold text-link">
					Review rejected
				</a>
				<a href="/jobs?fresh=today" class="text-xs font-semibold text-link">Today's jobs</a>
			</div>
		</div>
		<div class="flex w-full rounded-full border border-line bg-surface p-1 text-xs font-semibold sm:w-auto">
			{#each [{ key: 'strict', label: 'Strict' }, { key: 'balanced', label: 'Balanced' }, { key: 'broad', label: 'Broad' }] as mode}
				<button
					type="button"
					disabled={savingMode}
					onclick={() => setMatchMode(mode.key as 'strict' | 'balanced' | 'broad')}
					class="flex-1 whitespace-nowrap rounded-full px-3 py-1.5 transition-colors sm:flex-none"
					class:bg-brand={matchMode === mode.key}
					class:text-on-brand={matchMode === mode.key}
					class:text-ink-muted={matchMode !== mode.key}
				>
					{mode.label}
				</button>
			{/each}
		</div>
	</div>
	{#if modeError}
		<p class="mt-2 text-sm font-medium text-bad" role="alert">{modeError}</p>
	{/if}

	<div class="mt-4 grid gap-4 lg:grid-cols-2">
		{#each jobsToShow as job}
			<div class="min-w-0">
				<MatchSpotlight {job} />
			</div>
		{:else}
			<div class="rounded-2xl border border-line bg-surface p-6 text-sm text-ink-muted">
				No active matches yet. The scheduler will add them automatically after the next scrape and
				matching pass.
			</div>
		{/each}
	</div>

	<div class="mt-8 grid gap-4 md:grid-cols-2">
		<section
			id="documents"
			class="min-w-0 scroll-mt-24 rounded-2xl border border-line bg-surface p-4 sm:p-5"
		>
			<div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
				<h2 class="font-display text-lg font-bold text-ink">Documents</h2>
				<div class="flex flex-wrap items-center gap-x-3 gap-y-1">
					<a href="/applications" class="text-xs font-semibold text-link">Application kits</a>
					<a href="/documents" class="text-xs font-semibold text-link">View all</a>
				</div>
			</div>
			<p class="mt-1 text-sm text-ink-muted">Your latest tailored files.</p>
			<div class="mt-4 space-y-3">
				{#each docs as document}
					<div
						class="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 px-3 py-3"
					>
						<div class="min-w-0 flex-1">
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

		<section
			id="prep"
			class="min-w-0 scroll-mt-24 rounded-2xl border border-line bg-surface p-4 sm:p-5"
		>
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

	<section
		id="profile"
		class="mt-8 min-w-0 scroll-mt-24 rounded-2xl border border-line bg-surface p-4 sm:p-5"
	>
		<div class="flex flex-wrap items-start justify-between gap-4">
			<div class="min-w-0">
				<h2 class="font-display text-lg font-bold text-ink">Profile readiness</h2>
				<p class="mt-1 break-words text-sm text-ink-muted">
					{data.profile.headline ?? 'Add a headline and target roles'}
					{data.profile.location ? ` - ${data.profile.location}` : ''}
				</p>
			</div>
			<span class="shrink-0 rounded-full bg-match-light px-3 py-1 text-sm font-bold text-match-text">
				{data.profile.readiness}%
			</span>
		</div>
		<div class="mt-4 grid gap-3 sm:grid-cols-3">
			<div class="min-w-0 rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add freelance projects</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock more junior roles</p>
			</div>
			<div class="min-w-0 rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add driver licence</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock field roles</p>
			</div>
			<div class="min-w-0 rounded-xl border border-line bg-surface-2 px-3 py-3">
				<p class="text-xs font-semibold text-ink-muted">Add CCTV/NVR experience</p>
				<p class="mt-1 text-sm font-semibold text-ink">Unlock technician roles</p>
			</div>
		</div>
	</section>
</div>

{#if showPilot}
	<div class="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-4 sm:items-center">
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="pilot-title"
			class="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-xl"
		>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">WhatsApp pilot</p>
			<h2 id="pilot-title" class="mt-2 font-display text-2xl font-bold text-ink">
				Get match alerts on WhatsApp.
			</h2>
			<p class="mt-2 text-sm leading-relaxed text-ink-muted">
				The first 15 accounts can join. We send match and application updates only. You can opt in
				or out in Settings at any time.
			</p>
			<form class="mt-5" onsubmit={joinPilot}>
				<label class="block text-sm font-semibold text-ink">
					WhatsApp number
					<input
						type="tel"
						required
						bind:value={pilotPhone}
						placeholder="2637..."
						class="mt-1 h-12 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
					/>
				</label>
				{#if pilotError}
					<p class="mt-2 text-sm font-medium text-bad" role="alert">{pilotError}</p>
				{/if}
				<div class="mt-4 flex flex-wrap gap-2">
					<button
						type="submit"
						disabled={pilotBusy}
						class="inline-flex h-11 items-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
					>
						{pilotBusy ? 'Joining...' : 'Join pilot'}
					</button>
					<button
						type="button"
						onclick={dismissPilot}
						class="inline-flex h-11 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
					>
						Not now
					</button>
				</div>
			</form>
			<p class="mt-4 text-xs text-ink-muted">
				Manage this anytime in <a href="/settings" class="font-semibold text-link">Settings</a>.
			</p>
		</div>
	</div>
{/if}

