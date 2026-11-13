<script lang="ts">
	import { page } from '$app/state';
	import Icon from './Icon.svelte';

	const items = [
		{ href: '/dashboard', label: 'Jobs', icon: 'briefcase', match: '/dashboard' },
		{ href: '/matches', label: 'Matches', icon: 'target', match: '/matches' },
		{ href: '/applications', label: 'Kits', icon: 'file', match: '/applications' },
		// Prep and Profile live inside the dashboard as sections.
		{ href: '/dashboard#prep', label: 'Prep', icon: 'mic', match: '__none' },
		{ href: '/settings', label: 'Profile', icon: 'user', match: '/settings' }
	];

	const current = $derived(page.url.pathname);
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur md:hidden"
	aria-label="Primary"
>
	<div class="mx-auto grid max-w-md grid-cols-5">
		{#each items as item}
			{@const active =
				item.match !== '__none' &&
				(current === item.match || current.startsWith(`${item.match}/`))}
			<a
				href={item.href}
				aria-current={active ? 'page' : undefined}
				class="flex min-h-14 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors {active
					? 'text-brand'
					: 'text-ink-muted hover:text-ink'}"
			>
				<Icon name={item.icon} class="size-5" />
				<span>{item.label}</span>
			</a>
		{/each}
	</div>
</nav>
