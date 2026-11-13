<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { authClient } from '../../lib/auth-client';
	import PasswordInput from '../../lib/components/PasswordInput.svelte';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		error = '';
		loading = true;
		const result = await authClient.signIn.email({ email, password, callbackURL: '/dashboard' });
		loading = false;

		if (result.error) {
			error = result.error.message ?? 'Unable to sign in';
			return;
		}

		await invalidateAll();
		await goto('/dashboard');
	}
</script>

<svelte:head>
	<title>Sign in - Mukana</title>
	<meta name="description" content="Sign in to your Mukana workspace." />
</svelte:head>

<div
	class="mx-auto flex min-h-[calc(100dvh-8rem)] w-full max-w-md flex-col justify-center px-4 py-12"
>
	<div class="rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Welcome back</p>
		<h1 class="mt-2 font-display text-2xl font-bold tracking-tight text-ink">Sign in to Mukana.</h1>
		<p class="mt-2 text-sm leading-relaxed text-ink-muted">
			Pick up your matches, documents and interview prep where you left off.
		</p>

		<form class="mt-6 space-y-4" onsubmit={submit}>
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
				<label for="login-password">Password</label>
				<PasswordInput
					id="login-password"
					name="password"
					autocomplete="current-password"
					bind:value={password}
				/>
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
				{loading ? 'Signing in...' : 'Sign in'}
			</button>
		</form>

		<p class="mt-5 text-sm text-ink-muted">
			New here?
			<a href="/signup" class="font-semibold text-link underline-offset-4 hover:underline">
				Create an account
			</a>
		</p>
	</div>
</div>
