<script lang="ts">
	import { ROLE_FAMILY_GROUPS, type RoleFamily } from '../role-families';

	let { selected = [], onchange }: { selected?: string[]; onchange?: (values: string[]) => void } =
		$props();

	let chosen = $state<string[]>([...selected]);

	// Keep in step when the parent recomputes the selection (e.g. after a CV upload).
	$effect(() => {
		const next = [...selected];
		if (next.length !== chosen.length || next.some((value) => !chosen.includes(value))) {
			chosen = next;
		}
	});

	function commit(next: string[]) {
		chosen = next;
		onchange?.(next);
	}

	let openGroups = $state<string[]>([]);

	function countIn(groupValue: string): number {
		const group = ROLE_FAMILY_GROUPS.find((item) => item.value === groupValue);
		if (!group) return 0;
		return group.families.filter((family) => chosen.includes(family.value)).length;
	}

	function toggleGroup(groupValue: string) {
		openGroups = openGroups.includes(groupValue)
			? openGroups.filter((value) => value !== groupValue)
			: [...openGroups, groupValue];
	}

	function toggleFamily(value: RoleFamily, checked: boolean) {
		const next = checked
			? chosen.includes(value)
				? chosen
				: [...chosen, value]
			: chosen.filter((item) => item !== value);
		commit(next);
	}

	const total = $derived(chosen.length);
</script>

{#each chosen as value}
	<input type="hidden" name="targetFamilies" {value} />
{/each}

<div class="space-y-2">
	{#each ROLE_FAMILY_GROUPS as group}
		{@const open = openGroups.includes(group.value)}
		{@const picked = countIn(group.value)}
		<div class="overflow-hidden rounded-xl border border-line bg-surface">
			<button
				type="button"
				onclick={() => toggleGroup(group.value)}
				aria-expanded={open}
				class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2"
			>
				<span class="min-w-0">
					<span class="block text-sm font-semibold text-ink">{group.label}</span>
					<span class="mt-0.5 block text-xs text-ink-muted">{group.hint}</span>
				</span>
				<span class="flex shrink-0 items-center gap-2">
					{#if picked}
						<span
							class="rounded-full bg-match-light px-2 py-0.5 text-xs font-semibold text-match-text"
						>
							{picked}
						</span>
					{/if}
					<svg
						viewBox="0 0 20 20"
						fill="currentColor"
						class="size-4 text-ink-muted transition-transform {open ? 'rotate-180' : ''}"
						aria-hidden="true"
					>
						<path
							fill-rule="evenodd"
							d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
							clip-rule="evenodd"
						/>
					</svg>
				</span>
			</button>

			{#if open}
				<div class="grid gap-2 border-t border-line p-3 sm:grid-cols-2">
					{#each group.families as family}
						<label
							class="flex min-h-11 cursor-pointer items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink transition-colors has-checked:border-brand has-checked:bg-match-light"
						>
							<input
								type="checkbox"
								value={family.value}
								checked={chosen.includes(family.value)}
								onchange={(event) =>
									toggleFamily(family.value, (event.currentTarget as HTMLInputElement).checked)}
								class="size-4 shrink-0 accent-brand"
							/>
							<span>{family.label}</span>
						</label>
					{/each}
				</div>
			{/if}
		</div>
	{/each}
</div>

<p class="mt-2 text-xs text-ink-muted">
	{total === 0 ? 'No fields selected yet.' : `${total} field${total === 1 ? '' : 's'} selected.`}
</p>
