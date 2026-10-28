<script lang="ts">
	import '@fontsource-variable/inter';
	import '@fontsource-variable/space-grotesk';
	import './layout.css';
	import { goto } from '$app/navigation';
	import { authClient } from '../lib/auth-client';
	import Logo from '../lib/components/Logo.svelte';
	import ThemeToggle from '../lib/components/ThemeToggle.svelte';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();

	async function signOut() {
		await authClient.signOut();
		await goto('/');
	}
</script>

<svelte:head>
	<title>Mukana - Less applying. More interviewing.</title>
	<meta
		name="description"
		content="Mukana finds roles that fit, tailors your CV and cover letter, prepares the application, and gets you ready for the interview. Built in Zimbabwe for local and remote job seekers."
	/>
	<meta property="og:type" content="website" />
	<meta property="og:site_name" content="Mukana" />
	<meta property="og:title" content="Mukana - Less applying. More interviewing." />
	<meta
		property="og:description"
		content="Find roles that fit, tailor your application, and prepare for the interview. You review. We prepare. You send."
	/>
	<meta property="og:url" content="https://mukana.mikeyverse.co.zw" />
	<meta property="og:image" content="https://mukana.mikeyverse.co.zw/social-preview.svg" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="Mukana - Less applying. More interviewing." />
	<meta
		name="twitter:description"
		content="Find roles that fit, tailor your application, and prepare for the interview."
	/>
	<meta name="twitter:image" content="https://mukana.mikeyverse.co.zw/social-preview.svg" />
	<link rel="canonical" href="https://mukana.mikeyverse.co.zw" />
</svelte:head>

<a
	href="#main"
	class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-brand focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-on-brand"
>
	Skip to content
</a>

<div class="min-h-dvh bg-canvas">
	<header class="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur">
		<div class="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
			<Logo />
			<nav class="hidden items-center gap-6 text-sm font-medium text-ink-muted md:flex">
				<a href="/#how" class="transition-colors hover:text-ink">How it works</a>
				<a href="/#features" class="transition-colors hover:text-ink">Features</a>
				<a href="/#pricing" class="transition-colors hover:text-ink">Pricing</a>
				{#if data.user}
					<a href="/dashboard" class="transition-colors hover:text-ink">Workspace</a>
					<a href="/settings" class="transition-colors hover:text-ink">Settings</a>
				{/if}
			</nav>
			<div class="flex items-center gap-2">
				<ThemeToggle />
				{#if data.user}
					<a
						href="/settings"
						class="hidden h-10 items-center rounded-full border border-line-strong bg-surface px-4 text-sm font-semibold text-ink transition-colors hover:bg-surface-2 sm:inline-flex"
					>
						Settings
					</a>
					<button
						type="button"
						onclick={signOut}
						class="inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover"
					>
						Sign out
					</button>
				{:else}
					<a
						href="/login"
						class="hidden text-sm font-semibold text-ink-muted transition-colors hover:text-ink sm:inline-flex"
					>
						Sign in
					</a>
					<a
						href="/signup"
						class="inline-flex h-10 items-center rounded-full bg-brand px-4 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover"
					>
						Start free
					</a>
				{/if}
			</div>
		</div>
	</header>

	<main id="main">
		{@render children()}
	</main>

	<footer class="border-t border-line bg-surface-2">
		<div
			class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-center md:justify-between"
		>
			<div class="max-w-sm">
				<Logo />
				<p class="mt-3 text-sm leading-relaxed text-ink-muted">
					Job applications, prepared. Built in Zimbabwe for graduates and early-career professionals
					chasing local and remote roles.
				</p>
			</div>
			<div class="flex flex-wrap gap-x-8 gap-y-3 text-sm font-medium text-ink-muted">
				<a href="/#how" class="hover:text-ink">How it works</a>
				<a href="/#pricing" class="hover:text-ink">Pricing</a>
				<a href="/dashboard" class="hover:text-ink">Dashboard</a>
				<a href="mailto:hello@mikeyverse.co.zw" class="hover:text-ink">Contact</a>
			</div>
		</div>
		<div class="border-t border-line">
			<p class="mx-auto max-w-6xl px-4 py-4 text-xs text-ink-muted sm:px-6">
				&copy; {new Date().getFullYear()} Mukana. You review every application before it leaves your hands.
			</p>
		</div>
	</footer>
</div>
