<script lang="ts">
	import CvTemplatePicker from '../../lib/components/CvTemplatePicker.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let phone = $state('');
	let contactPhone = $state('');
	let linkedinUrl = $state('');
	let cvTemplate = $state('harvard');
	let savingProfile = $state(false);
	let profileNotice = $state('');
	let profileError = $state('');

	$effect(() => {
		contactPhone = data.profile.phone ?? '';
		linkedinUrl = data.profile.linkedinUrl ?? '';
		cvTemplate = data.profile.cvTemplate ?? 'harvard';
	});

	async function saveProfile() {
		savingProfile = true;
		profileNotice = '';
		profileError = '';
		const response = await fetch('/api/profile', {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				phone: contactPhone,
				linkedinUrl,
				cvTemplate
			})
		});
		const result = (await response.json().catch(() => ({}))) as { error?: string };
		savingProfile = false;
		if (!response.ok) {
			profileError = result.error ?? 'Could not save your CV settings';
			return;
		}
		profileNotice = 'Saved. Newly generated documents will use this template.';
	}
	let pilotOverride = $state<{
		joined: boolean;
		slot: number | null;
		status: string | null;
		phone: string | null;
	} | null>(null);
	const pilot = $derived(pilotOverride ?? data.whatsapp);
	let pilotError = $state('');
	let joining = $state(false);

	async function optOutPilot() {
		pilotError = '';
		const response = await fetch('/api/whatsapp/pilot', { method: 'DELETE' });
		const result = (await response.json().catch(() => ({}))) as { error?: string };
		if (!response.ok) {
			pilotError = result.error ?? 'Could not opt out';
			return;
		}
		pilotOverride = { joined: false, slot: null, status: null, phone: null };
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

	<section class="mt-8 rounded-2xl border border-line bg-surface p-5">
		<h2 class="font-display text-lg font-bold text-ink">CV and contact details</h2>
		<p class="mt-1 text-sm text-ink-muted">
			These details are used on every tailored CV and cover letter. The template applies to new
			documents.
		</p>
		<div class="mt-4 grid gap-4 sm:grid-cols-2">
			<label class="block text-sm font-semibold text-ink">
				Phone
				<input
					type="tel"
					bind:value={contactPhone}
					placeholder="+263..."
					class="mt-1 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
				/>
			</label>
			<label class="block text-sm font-semibold text-ink">
				LinkedIn
				<input
					bind:value={linkedinUrl}
					placeholder="www.linkedin.com/in/..."
					class="mt-1 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm font-normal text-ink outline-none focus:border-brand"
				/>
			</label>
			<div class="sm:col-span-2">
				<p class="text-sm font-semibold text-ink">CV template</p>
				<div class="mt-2">
					<CvTemplatePicker
						value={cvTemplate}
						onchange={(template) => (cvTemplate = template)}
					/>
				</div>
			</div>
		</div>
		{#if profileError}
			<p class="mt-3 text-sm font-medium text-bad" role="alert">{profileError}</p>
		{/if}
		{#if profileNotice}
			<p class="mt-3 text-sm font-medium text-match-text" role="status">{profileNotice}</p>
		{/if}
		<button
			type="button"
			onclick={saveProfile}
			disabled={savingProfile}
			class="mt-4 inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
		>
			{savingProfile ? 'Saving...' : 'Save CV settings'}
		</button>
	</section>

	<section class="mt-4 rounded-2xl border border-line bg-surface p-5">
		<h2 class="font-display text-lg font-bold text-ink">Application kits</h2>
		<p class="mt-1 text-sm text-ink-muted">
			Every generated match produces a downloadable kit with your tailored CV, cover letter and
			any required extra documents. Download the PDF or the ready-to-send .eml and send it
			yourself.
		</p>
		<a
			href="/applications"
			class="mt-4 inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover"
		>
			Open application kits
		</a>
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
				<button
					type="button"
					onclick={optOutPilot}
					class="mt-3 inline-flex h-9 items-center rounded-full border border-line-strong bg-surface px-4 text-xs font-semibold text-ink hover:bg-surface-2"
				>
					Opt out of WhatsApp notifications
				</button>
			</div>
			{#if pilotError}
				<p class="mt-2 text-sm font-medium text-bad" role="alert">{pilotError}</p>
			{/if}
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
