<script lang="ts">
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const families = [
		{ value: 'software', label: 'Software & mobile' },
		{ value: 'data', label: 'Data & analytics' },
		{ value: 'it_support', label: 'IT support' },
		{ value: 'cyber', label: 'Cyber security' },
		{ value: 'sales', label: 'Sales & field' },
		{ value: 'teaching', label: 'Teaching' },
		{ value: 'compliance', label: 'Compliance & data protection' },
		{ value: 'electronics', label: 'Electronics & CCTV' },
		{ value: 'admin', label: 'Admin & operations' },
		{ value: 'other', label: 'Other' }
	] as const;

	const values = $derived(
		form?.values as
			| {
					headline?: string;
					location?: string;
					yearsExperience?: number;
					targetFamilies?: string[];
					matchMode?: string;
			  }
			| undefined
	);

	const selectedFamilies = $derived(
		values?.targetFamilies ?? data.profile?.targetFamilies ?? []
	);
	const matchMode = $derived(values?.matchMode ?? data.profile?.matchMode ?? 'balanced');
</script>

<svelte:head>
	<title>Set up your profile - Mukana</title>
	<meta
		name="description"
		content="Tell Mukana your target roles and experience level so matching respects where you actually are."
	/>
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Step 1 of 2</p>
			<h1 class="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Tell us where you are.
			</h1>
			<p class="mt-3 max-w-xl text-sm leading-relaxed text-ink-muted">
				This controls which roles reach you. Add the work you actually have - full-time,
				internship, freelance, volunteer or academic - and we will stop sending the wrong level.
			</p>
		</div>
		<a href="/dashboard" class="text-sm font-semibold text-link underline-offset-4 hover:underline">
			Skip for now
		</a>
	</div>

	{#if form?.error}
		<p class="mt-6 rounded-xl bg-bad/10 px-4 py-3 text-sm font-medium text-bad" role="alert">
			{form.error}
		</p>
	{/if}

	<form method="POST" class="mt-8 space-y-6">
		<div class="grid gap-4 sm:grid-cols-2">
			<label class="block text-sm font-semibold text-ink">
				Headline
				<input
					name="headline"
					required
					minlength="2"
					maxlength="160"
					value={values?.headline ?? data.profile?.headline ?? ''}
					placeholder="Software developer - data analyst"
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
			<label class="block text-sm font-semibold text-ink">
				Location
				<input
					name="location"
					required
					minlength="2"
					maxlength="120"
					value={values?.location ?? data.profile?.location ?? 'Harare, Zimbabwe'}
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
		</div>

		<div class="grid gap-4 sm:grid-cols-2">
			<label class="block text-sm font-semibold text-ink">
				Years of experience
				<input
					name="yearsExperience"
					type="number"
					min="0"
					max="50"
					value={values?.yearsExperience ?? data.profile?.yearsExperience ?? 0}
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
			<label class="block text-sm font-semibold text-ink">
				Match mode
				<select
					name="matchMode"
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				>
					<option value="strict" selected={matchMode === 'strict'}>Strict - closest fit only</option>
					<option value="balanced" selected={matchMode === 'balanced'}>
						Balanced - adjacent roles too
					</option>
					<option value="broad" selected={matchMode === 'broad'}>
						Broad - include stretches
					</option>
				</select>
			</label>
		</div>

		<fieldset>
			<legend class="text-sm font-semibold text-ink">Role families you want</legend>
			<p class="mt-1 text-xs text-ink-muted">Pick as many as apply. You can change this later.</p>
			<div class="mt-3 grid gap-2 sm:grid-cols-2">
				{#each families as family}
					<label
						class="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink transition-colors has-checked:border-brand has-checked:bg-match-light"
					>
						<input
							type="checkbox"
							name="targetFamilies"
							value={family.value}
							checked={selectedFamilies.includes(family.value)}
							class="size-4 accent-brand"
						/>
						<span>{family.label}</span>
					</label>
				{/each}
			</div>
		</fieldset>

		<div class="flex flex-wrap items-center gap-3 pt-2">
			<button
				type="submit"
				class="inline-flex h-12 items-center justify-center rounded-full bg-brand px-6 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover"
			>
				Save and continue
			</button>
			<a href="/dashboard" class="text-sm font-semibold text-ink-muted hover:text-ink">
				I will do this later
			</a>
		</div>
	</form>
</div>
