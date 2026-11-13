<script lang="ts">
	import CvTemplatePicker from '../../lib/components/CvTemplatePicker.svelte';
	import RoleFamilyPicker from '../../lib/components/RoleFamilyPicker.svelte';
	import type { CvTemplate } from '../../lib/cv-templates';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const families = [
		{ value: 'software', label: 'Software & mobile' },
		{ value: 'data', label: 'Data & analytics' },
		{ value: 'it_support', label: 'IT support' },
		{ value: 'cyber', label: 'Cyber security' },
		{ value: 'sales', label: 'Sales & field' },
		{ value: 'teaching', label: 'Teaching & education' },
		{ value: 'compliance', label: 'Compliance & data protection' },
		{ value: 'electronics', label: 'Electronics & CCTV' },
		{ value: 'admin', label: 'Admin & operations' },
		{ value: 'finance', label: 'Finance & accounting' },
		{ value: 'banking', label: 'Banking & fintech' },
		{ value: 'hr', label: 'HR & recruiting' },
		{ value: 'marketing', label: 'Marketing & communications' },
		{ value: 'legal', label: 'Legal & regulatory' },
		{ value: 'healthcare', label: 'Healthcare & medical' },
		{ value: 'engineering', label: 'Engineering' },
		{ value: 'mining', label: 'Mining & geology' },
		{ value: 'agriculture', label: 'Agriculture & environment' },
		{ value: 'logistics', label: 'Logistics & supply chain' },
		{ value: 'hospitality', label: 'Hospitality & tourism' },
		{ value: 'customer_service', label: 'Customer service' },
		{ value: 'trades', label: 'Skilled trades' },
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
					resumeText?: string;
					phone?: string;
					linkedinUrl?: string;
					cvTemplate?: string;
			  }
			| undefined
	);

	const selectedFamilies = $derived(
		values?.targetFamilies ?? data.profile?.targetFamilies ?? []
	);
	const matchMode = $derived(values?.matchMode ?? data.profile?.matchMode ?? 'balanced');

	let fileInput: HTMLInputElement | undefined = $state();
	let extracting = $state(false);
	let extractError = $state('');
	let extractNotice = $state('');

	let headline = $state(values?.headline ?? data.profile?.headline ?? '');
	let location = $state(values?.location ?? data.profile?.location ?? 'Harare, Zimbabwe');
	let yearsExperience = $state(values?.yearsExperience ?? data.profile?.yearsExperience ?? 0);
	let phone = $state(values?.phone ?? data.profile?.phone ?? '');
	let linkedinUrl = $state(values?.linkedinUrl ?? data.profile?.linkedinUrl ?? '');
	let chosenFamilies = $state<string[]>([...selectedFamilies]);
	let applied = $state(false);
	let cvLoaded = $state('');
	let resumeText = $state(values?.resumeText ?? data.profile?.resumeText ?? '');
	let cvTemplate = $state<string>(
		values?.cvTemplate ?? data.profile?.cvTemplate ?? 'harvard'
	);

	type RefereeDraft = {
		id: string;
		name: string;
		role: string | null;
		organisation: string | null;
		email: string | null;
		phone: string | null;
	};
	let referees = $state<RefereeDraft[]>(
		((data.profile?.references ?? []) as RefereeDraft[]).map((referee) => ({ ...referee }))
	);
	let referencesEnabled = $state<boolean>(data.profile?.referencesEnabled ?? false);

	function addReferee() {
		const form = document.querySelector('form');
		const read = (name: string) =>
			(form?.querySelector(`[name="${name}"]`) as HTMLInputElement | null)?.value?.trim() ?? '';
		const name = read('ref_name');
		if (!name) {
			extractError = 'Enter the referee name first.';
			return;
		}
		referees = [
			...referees,
			{
				id: crypto.randomUUID(),
				name,
				role: read('ref_role') || null,
				organisation: read('ref_org') || null,
				phone: read('ref_phone') || null,
				email: read('ref_email') || null
			}
		];
		for (const field of ['ref_name', 'ref_role', 'ref_org', 'ref_phone', 'ref_email']) {
			const input = form?.querySelector(`[name="${field}"]`) as HTMLInputElement | null;
			if (input) input.value = '';
		}
		extractError = '';
	}

	function removeReferee(index: number) {
		referees = referees.filter((_, position) => position !== index);
	}

	$effect(() => {
		const input = document.querySelector(
			'input[name="referencesJson"]'
		) as HTMLInputElement | null;
		if (input) input.value = JSON.stringify(referees);
	});

	let generatingCv = $state(false);
	let cvError = $state('');
	let cvNotice = $state('');
	let latestCv = $state<{ documentId: string; theme: string; pages: number } | null>(null);
	let polish = $state(true);

	async function regenerateCv() {
		cvError = '';
		cvNotice = '';
		generatingCv = true;
		try {
			const response = await fetch('/api/cv/base', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ theme: cvTemplate, polish })
			});
			const payload = (await response.json()) as {
				error?: string;
				documentId?: string;
				theme?: string;
				pages?: number;
			};
			if (!response.ok || !payload.documentId) {
				cvError = payload.error ?? 'Could not generate your CV';
				return;
			}
			latestCv = {
				documentId: payload.documentId,
				theme: payload.theme ?? cvTemplate,
				pages: payload.pages ?? 1
			};
			cvNotice = polish
				? `Polished CV ready - ${payload.pages ?? 1} page(s) in ${payload.theme ?? cvTemplate}.`
				: `CV ready - ${payload.pages ?? 1} page(s) in ${payload.theme ?? cvTemplate}.`;
		} catch {
			cvError = 'Could not reach the server. Try again.';
		} finally {
			generatingCv = false;
		}
	}

	async function autoCollect() {
		extractError = '';
		extractNotice = '';
		const file = fileInput?.files?.[0];
		if (!file) {
			extractError = 'Choose your CV file first.';
			return;
		}

		extracting = true;
		const body = new FormData();
		body.append('file', file);
		body.append('purpose', 'resume');

		let payload: {
			error?: string;
			resumeUpdated?: boolean;
			resumeText?: string | null;
			suggestions?: {
				headline: string | null;
				location: string | null;
				yearsExperience: number | null;
				phone: string | null;
				linkedinUrl: string | null;
				targetFamilies: string[];
			} | null;
		};
		try {
			const response = await fetch('/api/files', { method: 'POST', body });
			payload = await response.json();
			if (!response.ok) {
				extractError = payload.error ?? 'Upload failed';
				return;
			}
		} catch {
			extractError = 'Could not upload that file. Check your connection and try again.';
			return;
		} finally {
			extracting = false;
		}

		const suggestions = payload.suggestions;
		if (!payload.resumeUpdated || !suggestions) {
			extractError =
				'We stored your CV but could not read the details from it. Fill the fields in below.';
			return;
		}

		if (suggestions.headline) headline = suggestions.headline;
		if (suggestions.location) location = suggestions.location;
		if (suggestions.yearsExperience !== null) yearsExperience = suggestions.yearsExperience;
		if (suggestions.phone) phone = suggestions.phone;
		if (suggestions.linkedinUrl) linkedinUrl = suggestions.linkedinUrl;
		if (suggestions.targetFamilies.length) {
			chosenFamilies = [...new Set([...chosenFamilies, ...suggestions.targetFamilies])].slice(0, 8);
		}
		if (payload.resumeText) resumeText = payload.resumeText;
		applied = true;
		cvLoaded = `${file.name} uploaded and read`;
		extractNotice =
			'Details collected from your CV. Check them, adjust anything, then save.';
	}
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

	<section class="mt-8 rounded-2xl border border-brand/30 bg-match-light p-5">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div>
				<h2 class="font-display text-lg font-bold text-ink">Auto-collect my details</h2>
				<p class="mt-1 max-w-xl text-sm leading-relaxed text-ink-muted">
					Upload your current CV and we will read it, fill this form in for you, and keep it for
					generating applications. PDF, DOCX, images or text up to 15 MB.
				</p>
			</div>
			{#if applied}
				<span
					class="rounded-full bg-surface px-3 py-1 text-xs font-semibold text-match-text"
				>
					Details collected
				</span>
			{/if}
		</div>

		<div class="mt-4 flex flex-wrap items-center gap-3">
			<input
				bind:this={fileInput}
				type="file"
				accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.txt"
				class="min-w-0 flex-1 text-sm text-ink"
			/>
			<button
				type="button"
				onclick={autoCollect}
				disabled={extracting}
				class="inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover disabled:opacity-60"
			>
				{extracting ? 'Reading your CV...' : 'Auto collect details'}
			</button>
		</div>

		{#if extractError}
			<p class="mt-3 text-sm font-medium text-bad" role="alert">{extractError}</p>
		{/if}
		{#if extractNotice}
			<p class="mt-3 text-sm font-medium text-match-text" role="status">{extractNotice}</p>
		{/if}
	</section>

	<form method="POST" class="mt-8 space-y-6">
		<div class="grid gap-4 sm:grid-cols-2">
			<label class="block text-sm font-semibold text-ink">
				Headline
				<input
					name="headline"
					required
					minlength="2"
					maxlength="160"
					bind:value={headline}
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
					bind:value={location}
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
					bind:value={yearsExperience}
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

		<div class="grid gap-4 sm:grid-cols-2">
			<label class="block text-sm font-semibold text-ink">
				Phone
				<input
					name="phone"
					type="tel"
					maxlength="60"
					bind:value={phone}
					placeholder="+263..."
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
			<label class="block text-sm font-semibold text-ink">
				LinkedIn
				<input
					name="linkedinUrl"
					maxlength="500"
					bind:value={linkedinUrl}
					placeholder="www.linkedin.com/in/..."
					class="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm font-normal text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
		</div>

		<fieldset>
			<legend class="text-sm font-semibold text-ink">CV template</legend>
			<p class="mt-1 text-xs font-normal leading-relaxed text-ink-muted">
				Pick the format you want. Every tailored CV uses it. You can change this later in
				Settings.
			</p>
			<div class="mt-3">
				<CvTemplatePicker value={cvTemplate} onchange={(template) => (cvTemplate = template)} />
			</div>
		</fieldset>

		<section class="rounded-2xl border border-line bg-surface-2 p-5">
			<h2 class="font-display text-base font-bold text-ink">Get your CV now</h2>
			<p class="mt-1 max-w-xl text-sm leading-relaxed text-ink-muted">
				Generate a finished CV in the format above without waiting for a job match. Save this
				step first if you have just uploaded your CV.
			</p>
			<label class="mt-3 flex items-center gap-2 text-sm text-ink">
				<input type="checkbox" bind:checked={polish} class="size-4 accent-brand" />
				Polish the wording with AI before rendering
			</label>
			<div class="mt-3 flex flex-wrap items-center gap-3">
				<button
					type="button"
					onclick={regenerateCv}
					disabled={generatingCv}
					class="inline-flex h-11 items-center justify-center rounded-full border border-line-strong bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:bg-surface-2 disabled:opacity-60"
				>
					{generatingCv ? 'Generating...' : 'Generate my CV'}
				</button>
				{#if latestCv}
					<a
						href={`/api/cv/base/${latestCv.documentId}`}
						class="inline-flex h-11 items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
					>
						Download PDF
					</a>
				{/if}
			</div>
			{#if cvError}
				<p class="mt-3 text-sm font-medium text-bad" role="alert">{cvError}</p>
			{/if}
			{#if cvNotice}
				<p class="mt-3 text-sm font-medium text-match-text" role="status">{cvNotice}</p>
			{/if}
		</section>

		<label class="block text-sm font-semibold text-ink">
			Resume text
			<p class="mt-1 text-xs font-normal leading-relaxed text-ink-muted">
				{cvLoaded
					? 'Collected from the CV you uploaded. Edit anything that is wrong - this drives matching and document generation.'
					: 'Paste your CV or a detailed career summary. This is used only for matching and document generation.'}
			</p>
			{#if cvLoaded}
				<span class="mt-2 inline-flex text-xs font-normal text-match-text">
					{cvLoaded}
				</span>
			{/if}
			<textarea
				name="resumeText"
				rows="10"
				maxlength="20000"
				bind:value={resumeText}
				placeholder="Experience, skills, education, projects, tools..."
				class="mt-2 w-full rounded-xl border border-line bg-surface px-3 py-3 text-sm font-normal leading-relaxed text-ink outline-none transition-colors focus:border-brand"
			></textarea>
		</label>

		<input type="hidden" name="referencesJson" value="[]" />

		<fieldset>
			<legend class="text-sm font-semibold text-ink">References</legend>
			<p class="mt-1 text-xs font-normal leading-relaxed text-ink-muted">
				Add your referees once. When this is on they appear on the CV instead of "Available upon
				request" - expected for teaching, public sector and NGO roles.
			</p>
			<label class="mt-3 flex items-center gap-2 text-sm text-ink">
				<input
					type="checkbox"
					name="referencesEnabled"
					bind:checked={referencesEnabled}
					class="size-4 accent-brand"
				/>
				Include my referees on generated CVs
			</label>

			{#if referees.length}
				<div class="mt-3 space-y-2">
					{#each referees as referee, index (referee.id)}
						<div class="rounded-xl border border-line bg-surface p-3">
							<div class="flex items-start justify-between gap-3">
								<p class="text-sm font-semibold text-ink">
									{referee.name}{#if referee.role}<span class="font-normal text-ink-muted">
											- {referee.role}</span
										>{/if}
								</p>
								<button
									type="button"
									onclick={() => removeReferee(index)}
									class="text-xs font-semibold text-bad hover:underline"
								>
									Remove
								</button>
							</div>
							{#if referee.organisation}
								<p class="mt-0.5 text-xs text-ink-muted">{referee.organisation}</p>
							{/if}
							{#if referee.phone || referee.email}
								<p class="mt-0.5 text-xs text-ink-muted">
									{[referee.phone, referee.email].filter(Boolean).join(' | ')}
								</p>
							{/if}
						</div>
					{/each}
				</div>
			{/if}

			<div class="mt-3 grid gap-2 sm:grid-cols-2">
				<input
					name="ref_name"
					placeholder="Referee name"
					class="h-11 rounded-xl border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-brand"
				/>
				<input
					name="ref_role"
					placeholder="Role, e.g. HOD Humanities"
					class="h-11 rounded-xl border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-brand"
				/>
				<input
					name="ref_org"
					placeholder="Organisation"
					class="h-11 rounded-xl border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-brand"
				/>
				<input
					name="ref_phone"
					placeholder="Phone"
					class="h-11 rounded-xl border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-brand"
				/>
				<input
					name="ref_email"
					placeholder="Email (optional)"
					class="h-11 rounded-xl border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-brand sm:col-span-2"
				/>
			</div>
			<button
				type="button"
				onclick={addReferee}
				class="mt-2 inline-flex h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink hover:bg-surface-2"
			>
				Add referee
			</button>
		</fieldset>

		<fieldset>
			<legend class="text-sm font-semibold text-ink">Role families you want</legend>
			<p class="mt-1 text-xs text-ink-muted">
				Open a group and tick the fields that apply. Pick as many as you like; you can change
				this later.
			</p>
			<div class="mt-3">
				<RoleFamilyPicker
					selected={chosenFamilies}
					onchange={(values) => (chosenFamilies = values)}
				/>
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
