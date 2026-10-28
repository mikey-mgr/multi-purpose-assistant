<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let phone = $state('');
	let pilotOverride = $state<{
		joined: boolean;
		slot: number | null;
		status: string | null;
		phone: string | null;
	} | null>(null);
	const pilot = $derived(pilotOverride ?? data.whatsapp);
	let pilotError = $state('');
	let joining = $state(false);

	const messages: Record<string, string> = {
		connected: 'Gmail connected. Mukana can now create application drafts.',
		'mock-connected': 'Gmail connected in mock mode. Drafts will be simulated.',
		denied: 'Gmail authorisation was cancelled.',
		state: 'The Gmail authorisation expired. Please try again.',
		refresh: 'Google did not return a refresh token. Please reconnect and approve offline access.',
		error: 'Could not connect Gmail. Please try again.'
	};

	async function disconnectGmail() {
		await fetch('/api/integrations/gmail', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: '{}'
		});
		location.reload();
	}

	async function joinPilot(event: SubmitEvent) {
		event.preventDefault();
		pilotError = '';
		joining = true;
		const response = await fetch('/api/whatsapp/pilot', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ phone })
		});
		const result = (await response.json()) as {
			error?: string;
			slot?: number | null;
			status?: string;
			phone?: string;
		};
		joining = false;

		if (!response.ok) {
			pilotError = result.error ?? 'Could not join the pilot';
			return;
		}

		pilotOverride = {
			joined: true,
			slot: result.slot ?? null,
			status: result.status ?? 'active',
			phone: result.phone ?? phone
		};
	}
</script>

<svelte:head>
	<title>Settings - Mukana</title>
	<meta name="description" content="Manage your Mukana integrations, notifications and plan." />
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-10 sm:px-6">
	<div>
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Settings</p>
		<h1 class="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
			Integrations and notifications.
		</h1>
		<p class="mt-3 max-w-xl text-sm leading-relaxed text-ink-muted">
			Connect Gmail to create application drafts, or join the 15-person WhatsApp pilot.
		</p>
	</div>

	{#if data.gmailStatus && messages[data.gmailStatus]}
		<p
			class="mt-6 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink"
			role="status"
		>
			{messages[data.gmailStatus]}
		</p>
	{/if}

	<section class="mt-8 rounded-2xl border border-line bg-surface p-5">
		<div class="flex flex-wrap items-start justify-between gap-4">
			<div>
				<h2 class="font-display text-lg font-bold text-ink">Gmail drafts</h2>
				<p class="mt-1 text-sm text-ink-muted">
					Mukana creates a draft in your Gmail with the cover letter and attachments. It never
					sends automatically.
				</p>
			</div>
			{#if data.gmail.connected}
				<button
					type="button"
					onclick={disconnectGmail}
					class="inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
				>
					Disconnect
				</button>
			{:else}
				<a
					href="/api/integrations/gmail/connect"
					class="inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover"
				>
					Connect Gmail
				</a>
			{/if}
		</div>
		{#if data.gmail.connected}
			<p class="mt-4 text-sm font-medium text-match-text">
				Connected as {data.gmail.email ?? 'Gmail account'}
			</p>
		{/if}
		<p class="mt-4 text-xs leading-relaxed text-ink-muted">
			Scope requested: create drafts only. Mukana cannot read your inbox or send email.
		</p>
	</section>

	<section class="mt-4 rounded-2xl border border-line bg-surface p-5">
		<h2 class="font-display text-lg font-bold text-ink">WhatsApp pilot</h2>
		<p class="mt-1 text-sm text-ink-muted">
			The first 15 accounts get optional WhatsApp notifications. It is a best-effort notifier, not
			the main channel.
		</p>

		{#if pilot.joined}
			<div class="mt-4 rounded-xl bg-match-light p-4">
				<p class="text-sm font-semibold text-match-text">
					{pilot.status === 'active' ? `Pilot slot ${pilot.slot}` : 'On the waitlist'}
				</p>
				<p class="mt-1 text-sm text-ink">{pilot.phone}</p>
			</div>
		{:else}
			<form class="mt-4 flex flex-wrap gap-3" onsubmit={joinPilot}>
				<label class="min-w-60 flex-1 text-sm font-semibold text-ink">
					WhatsApp number
					<input
						type="tel"
						required
						bind:value={phone}
						placeholder="2637..."
						class="mt-1 h-12 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
					/>
				</label>
				<button
					type="submit"
					disabled={joining}
					class="mt-6 inline-flex h-12 items-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
				>
					{joining ? 'Joining...' : 'Join pilot'}
				</button>
			</form>
			{#if pilotError}
				<p class="mt-2 text-sm font-medium text-bad" role="alert">{pilotError}</p>
			{/if}
		{/if}
	</section>
</div>
