<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { authClient } from '../../lib/auth-client';
	import PasswordInput from '../../lib/components/PasswordInput.svelte';

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		error = '';
		loading = true;
		const result = await authClient.signUp.email({
			name,
			email,
			password,
			callbackURL: '/onboarding'
		});
		loading = false;

		if (result.error) {
			error = result.error.message ?? 'Unable to create your account';
			return;
		}

		await invalidateAll();
		await goto('/onboarding');
	}
</script>

<svelte:head>
	<title>Create your account - Mukana</title>
	<meta
		name="description"
		content="Create a free Mukana account and start with roles that fit your level."
	/>
</svelte:head>

<div
	class="mx-auto flex min-h-[calc(100dvh-8rem)] w-full max-w-md flex-col justify-center px-4 py-12"
>
	<div class="rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Start free</p>
		<h1 class="mt-2 font-display text-2xl font-bold tracking-tight text-ink">
			Build your application workspace.
		</h1>
		<p class="mt-2 text-sm leading-relaxed text-ink-muted">
			No card. You review every document before it leaves your hands.
		</p>

		<form class="mt-6 space-y-4" onsubmit={submit}>
			<label class="block text-sm font-semibold text-ink">
				Full name
				<input
					type="text"
					name="name"
					autocomplete="name"
					required
					minlength="2"
					maxlength="120"
					bind:value={name}
					class="mt-1 h-12 w-full rounded-xl border border-line bg-canvas px-3 text-sm text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
			<label class="block text-sm font-semibold text-ink">
				Email
				<input
					type="email"
					name="email"
					autocomplete="email"
					required
					bind:value={email}
					class="mt-1 h-12 w-full rounded-xl border border-line bg-canvas px-3 text-sm text-ink outline-none transition-colors focus:border-brand"
				/>
			</label>
			<div class="block text-sm font-semibold text-ink">
				<label for="signup-password">Password</label>
				<PasswordInput
					id="signup-password"
					name="password"
					autocomplete="new-password"
					maxlength={128}
					bind:value={password}
				/>
				<span class="mt-1 block text-xs font-normal text-ink-muted">At least 8 characters.</span>
			</div>

			{#if error}
				<p class="rounded-lg bg-bad/10 px-3 py-2 text-sm font-medium text-bad" role="alert">
					{error}
				</p>
			{/if}

			<button
				type="submit"
				disabled={loading}
				class="inline-flex h-12 w-full items-center justify-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60"
			>
				{loading ? 'Creating account...' : 'Create account'}
			</button>
		</form>

		<p class="mt-5 text-sm text-ink-muted">
			Already have an account?
			<a href="/login" class="font-semibold text-link underline-offset-4 hover:underline">
				Sign in
			</a>
		</p>
	</div>
</div>
