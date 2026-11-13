<script lang="ts">
	import '@fontsource-variable/inter';
	import '@fontsource-variable/space-grotesk';
	import './layout.css';
	import { goto, invalidateAll } from '$app/navigation';
	import { authClient } from '../lib/auth-client';
	import BottomNav from '../lib/components/BottomNav.svelte';
	import Logo from '../lib/components/Logo.svelte';
	import ThemeToggle from '../lib/components/ThemeToggle.svelte';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();

	async function signOut() {
		await authClient.signOut();
		await invalidateAll();
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
	<meta property="og:image" content="https://mukana.mikeyverse.co.zw/social-preview.png" />
	<meta property="og:image:type" content="image/png" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta property="og:image:alt" content="Mukana - Less applying. More interviewing." />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="Mukana - Less applying. More interviewing." />
	<meta
		name="twitter:description"
		content="Find roles that fit, tailor your application, and prepare for the interview."
	/>
	<meta name="twitter:image" content="https://mukana.mikeyverse.co.zw/social-preview.png" />
	<meta name="twitter:image:alt" content="Mukana - Less applying. More interviewing." />
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
					<a href="/jobs" class="transition-colors hover:text-ink">Jobs</a>
					<a href="/matches" class="transition-colors hover:text-ink">Matches</a>
					<a href="/applications" class="transition-colors hover:text-ink">Kits</a>
					<a href="/dashboard" class="transition-colors hover:text-ink">Workspace</a>
					<a href="/settings" class="transition-colors hover:text-ink">Settings</a>
				{/if}
			</nav>
			<div class="flex items-center gap-2">
				<ThemeToggle />
				{#if data.user}
					<a
						href="/settings"
						aria-label="Settings"
						title="Settings"
						class="inline-flex size-10 items-center justify-center rounded-full border border-line-strong bg-surface text-ink transition-colors hover:bg-surface-2"
					>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class="size-5" aria-hidden="true">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="1.7"
								d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"
							/>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="1.7"
								d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6 1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.2.47.65.79 1.16.87H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
							/>
						</svg>
					</a>
					<button
						type="button"
						onclick={signOut}
						class="inline-flex h-10 items-center rounded-full bg-brand px-3 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover sm:px-4"
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

	{#if data.user}
		<BottomNav />
	{/if}

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
				<a href="/applications" class="hover:text-ink">Application kits</a>
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
