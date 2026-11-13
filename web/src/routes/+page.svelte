<script lang="ts">
	import Icon from '../lib/components/Icon.svelte';
	import MatchSpotlight from '../lib/components/MatchSpotlight.svelte';
	import { demoJobs } from '../lib/data/demo';

	const features = [
		{
			icon: 'target',
			title: 'Matches that respect your level',
			body: 'Strict, balanced or broad. Seniority and experience gates stop the one year in, applying for CEO problem before it starts.'
		},
		{
			icon: 'file',
			title: 'Tailored CV and cover letter',
			body: 'Every document is rewritten against the posting, from experience you actually have. No invented employers, roles or numbers.'
		},
		{
			icon: 'send',
			title: 'Applications you control',
			body: 'A ready Gmail draft or a downloadable application kit. Nothing sends until you review it and press send.'
		},
		{
			icon: 'mic',
			title: 'Interview prep that goes deep',
			body: 'Real questions, role frameworks, gaps to bridge, salary scripts, and role-play drills for the interview you actually face.'
		},
		{
			icon: 'chart',
			title: 'Outcome tracking',
			body: 'Log callbacks, interviews and offers. Learn what works for your profile instead of guessing from silence.'
		},
		{
			icon: 'key',
			title: 'BYOK, optional',
			body: 'Use our AI or bring your own API key. Your tokens, your cost, your control - no lock-in either way.'
		}
	];

	const steps = [
		{
			title: 'Build your profile',
			body: 'Import your CV or answer a few questions. Add the freelance, volunteer or academic work that proves your skills.'
		},
		{
			title: 'Choose your match mode',
			body: 'Strict for the closest fit, balanced for adjacent roles, broad for a stretch. Turn individual gates on or off.'
		},
		{
			title: 'Review the application',
			body: 'Check the tailored CV, cover letter, recipient and instructions. Everything stays in your hands.'
		},
		{
			title: 'Send and prepare',
			body: 'Open a Gmail draft or download the kit. Then rehearse the questions, gaps and salary conversation.'
		}
	];

	const plans = [
		{
			name: 'Free',
			price: '$0',
			cadence: 'forever',
			note: 'A clearer search, open to everyone.',
			features: [
				'5 delivered matches per day',
				'3 tailored documents per day',
				'1 interview prep per week',
				'Manual application kit',
				'Outcome tracking'
			],
			cta: 'Start free',
			featured: false
		},
		{
			name: 'Pro',
			price: '$6.99',
			cadence: '/ month',
			note: 'For an active search. Local pricing.',
			features: [
				'50 matches per day',
				'15 tailored documents per day',
				'4 interview preps per week',
				'Gmail draft delivery',
				'WhatsApp pilot for the first 15'
			],
			cta: 'Go Pro',
			featured: true
		},
		{
			name: 'Pro BYOK',
			price: '$3.99',
			cadence: '/ month',
			note: 'Bring your own key. Your tokens.',
			features: [
				'Unlimited documents on your key',
				'50 matches per day',
				'Full Pro workflow',
				'No platform token markup',
				'Same outcome tracking'
			],
			cta: 'Use my key',
			featured: false
		}
	];

	const faqs = [
		{
			q: 'Does Mukana apply for me?',
			a: 'No. Mukana prepares the application and places it in your Gmail drafts, or gives you a downloadable kit. You review every word and press send yourself.'
		},
		{
			q: 'Where do the jobs come from?',
			a: 'We aggregate local and remote listings. We show you the employer application route and instructions - not our scraper internals or source configuration.'
		},
		{
			q: 'Is my data safe?',
			a: 'We never ask for your email password. Gmail access is limited to creating drafts, and you can disconnect or delete your data at any time.'
		},
		{
			q: 'Do I need my own API key?',
			a: 'No. Pro includes platform AI usage. BYOK is optional for people who want to pay their provider directly or use their own model.'
		},
		{
			q: 'What is the WhatsApp pilot?',
			a: 'The first 15 accounts can opt into WhatsApp notifications through our local Evolution gateway. It is a best-effort notifier, not the main channel - email and web push are.'
		},
		{
			q: 'Can I use Mukana outside Zimbabwe?',
			a: 'Yes. Remote roles are included, but eligibility, time zones and work authorisation depend on each employer. We surface those requirements before you apply.'
		}
	];

	const jsonLd = {
		'@context': 'https://schema.org',
		'@graph': [
			{
				'@type': 'Organization',
				name: 'Mukana',
				url: 'https://mukana.mikeyverse.co.zw',
				logo: 'https://mukana.mikeyverse.co.zw/icon-512.png'
			},
			{
				'@type': 'WebSite',
				name: 'Mukana',
				url: 'https://mukana.mikeyverse.co.zw'
			},
			{
				'@type': 'SoftwareApplication',
				name: 'Mukana',
				applicationCategory: 'BusinessApplication',
				operatingSystem: 'Web',
				description:
					'Find roles that fit, tailor your CV and cover letter, prepare the application, and get ready for the interview.',
				offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' }
			},
			{
				'@type': 'FAQPage',
				mainEntity: faqs.map((faq) => ({
					'@type': 'Question',
					name: faq.q,
					acceptedAnswer: { '@type': 'Answer', text: faq.a }
				}))
			}
		]
	};
</script>

<svelte:head>
	{@html `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`}
</svelte:head>

<section class="relative overflow-hidden">
	<div
		class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(200,75,38,0.10),transparent_38%),radial-gradient(circle_at_88%_18%,rgba(27,107,72,0.08),transparent_40%)]"
	></div>
	<div
		class="relative mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:items-center lg:py-24"
	>
		<div>
			<p
				class="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted"
			>
				<span class="size-2 rounded-full bg-brand"></span>
				Job applications, prepared
			</p>
			<h1
				class="mt-5 max-w-xl text-4xl font-extrabold leading-[1.04] tracking-tight text-ink sm:text-5xl lg:text-6xl"
			>
				Less applying.<br />
				More <span class="text-brand">interviewing</span>.
			</h1>
			<p class="mt-5 max-w-xl text-base leading-relaxed text-ink-muted sm:text-lg">
				Mukana finds roles that actually fit, tailors your CV and cover letter, prepares the
				application, and gets you ready for the room. You review. We prepare. You send.
			</p>
			<div class="mt-7 flex flex-wrap gap-3">
				<a
					href="/signup"
					class="inline-flex h-12 items-center justify-center rounded-full bg-brand px-6 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-hover"
				>
					Find my next role
				</a>
				<a
					href="/#how"
					class="inline-flex h-12 items-center justify-center rounded-full border border-line-strong bg-surface px-6 text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
				>
					See how it works
				</a>
			</div>
			<dl class="mt-9 grid max-w-lg grid-cols-3 gap-3">
				<div class="rounded-xl border border-line bg-surface px-3 py-3">
					<dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Roles</dt>
					<dd class="mt-1 font-display text-sm font-bold text-ink">Local + remote</dd>
				</div>
				<div class="rounded-xl border border-line bg-surface px-3 py-3">
					<dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Sending</dt>
					<dd class="mt-1 font-display text-sm font-bold text-ink">Drafts only</dd>
				</div>
				<div class="rounded-xl border border-line bg-surface px-3 py-3">
					<dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Prep</dt>
					<dd class="mt-1 font-display text-sm font-bold text-ink">Real questions</dd>
				</div>
			</dl>
		</div>

		<div class="relative">
			<div
				class="pointer-events-none absolute -inset-6 rounded-[2rem] bg-[radial-gradient(circle,rgba(200,75,38,0.14),transparent_62%)] blur-2xl"
			></div>
			<MatchSpotlight job={demoJobs[0]} class="relative" />
			<p class="mt-3 text-center text-xs text-ink-muted">
				Hover or tap the card. On slow connections, tap to reveal.
			</p>
		</div>
	</div>
</section>

<section id="features" class="scroll-mt-20 border-t border-line bg-surface-2/60">
	<div class="mx-auto max-w-6xl px-4 py-16 sm:px-6">
		<div class="max-w-2xl">
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">One workspace</p>
			<h2 class="mt-3 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				From what is out there to interview-ready.
			</h2>
			<p class="mt-4 text-base leading-relaxed text-ink-muted">
				No more tab hopping, duplicate applications or generic CVs. Mukana keeps the search, the
				documents and the preparation in one place.
			</p>
		</div>
		<div class="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each features as feature}
				<article
					class="rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-line-strong"
				>
					<span
						class="grid size-10 place-items-center rounded-xl bg-match-light text-match-text"
					>
						<Icon name={feature.icon} class="size-5" />
					</span>
					<h3 class="mt-4 font-display text-lg font-bold text-ink">{feature.title}</h3>
					<p class="mt-2 text-sm leading-relaxed text-ink-muted">{feature.body}</p>
				</article>
			{/each}
		</div>
	</div>
</section>

<section id="how" class="scroll-mt-20">
	<div class="mx-auto max-w-6xl px-4 py-16 sm:px-6">
		<div class="max-w-2xl">
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">How it works</p>
			<h2 class="mt-3 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Four steps. No mystery.
			</h2>
		</div>
		<ol class="mt-10 grid gap-4 md:grid-cols-4">
			{#each steps as step, index}
				<li class="rounded-2xl border border-line bg-surface p-5">
					<span class="font-display text-sm font-bold text-brand">0{index + 1}</span>
					<h3 class="mt-3 font-display text-lg font-bold text-ink">{step.title}</h3>
					<p class="mt-2 text-sm leading-relaxed text-ink-muted">{step.body}</p>
				</li>
			{/each}
		</ol>
	</div>
</section>

<section id="pricing" class="scroll-mt-20 border-t border-line bg-surface-2/60">
	<div class="mx-auto max-w-6xl px-4 py-16 sm:px-6">
		<div class="max-w-2xl">
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Pricing</p>
			<h2 class="mt-3 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
				Start free. Pay when the search gets busy.
			</h2>
			<p class="mt-4 text-base leading-relaxed text-ink-muted">
				Local pricing is shown. International pricing is $11.99 for Pro and $7.99 for Pro BYOK.
			</p>
		</div>
		<div class="mt-10 grid gap-4 lg:grid-cols-3">
			{#each plans as plan}
				<article
					class="relative flex flex-col rounded-2xl border bg-surface p-6"
					class:border-brand={plan.featured}
					class:ring-1={plan.featured}
					class:ring-brand={plan.featured}
				>
					{#if plan.featured}
						<span
							class="absolute -top-3 left-6 rounded-full bg-brand px-3 py-1 text-xs font-semibold text-on-brand"
						>
							Most popular
						</span>
					{/if}
					<h3 class="font-display text-lg font-bold text-ink">{plan.name}</h3>
					<p class="mt-2 flex items-baseline gap-1">
						<span class="font-display text-3xl font-extrabold tracking-tight text-ink">
							{plan.price}
						</span>
						<span class="text-sm font-medium text-ink-muted">{plan.cadence}</span>
					</p>
					<p class="mt-2 text-sm text-ink-muted">{plan.note}</p>
					<ul class="mt-5 space-y-2 text-sm">
						{#each plan.features as feature}
							<li class="flex gap-2 text-ink">
								<Icon name="check" class="mt-0.5 size-4 shrink-0 text-match-text" />
								<span>{feature}</span>
							</li>
						{/each}
					</ul>
					<a
						href="/signup"
						class="mt-6 inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition-colors"
						class:bg-brand={plan.featured}
						class:text-on-brand={plan.featured}
						class:hover:bg-brand-hover={plan.featured}
						class:border={!plan.featured}
						class:border-line-strong={!plan.featured}
						class:text-ink={!plan.featured}
						class:hover:bg-surface-2={!plan.featured}
					>
						{plan.cta}
					</a>
				</article>
			{/each}
		</div>
		<p class="mt-5 text-center text-xs leading-relaxed text-ink-muted">
			Founding lifetime for the first 100 accounts: $34.99 Pro and $19.99 BYOK. Pay with Paynow,
			EcoCash, OneMoney or card.
		</p>
	</div>
</section>

<section id="faq" class="scroll-mt-20">
	<div class="mx-auto max-w-3xl px-4 py-16 sm:px-6">
		<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand">Clear answers</p>
		<h2 class="mt-3 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
			No fine-print scavenger hunt.
		</h2>
		<div class="mt-8 divide-y divide-line rounded-2xl border border-line bg-surface">
			{#each faqs as faq}
				<details class="group p-5">
					<summary
						class="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-semibold text-ink"
					>
						{faq.q}
						<span class="text-lg leading-none text-ink-muted transition-transform group-open:rotate-45">
							+
						</span>
					</summary>
					<p class="mt-3 text-sm leading-relaxed text-ink-muted">{faq.a}</p>
				</details>
			{/each}
		</div>
	</div>
</section>

<section class="border-t border-line">
	<div class="mx-auto max-w-6xl px-4 py-14 sm:px-6">
		<div class="rounded-3xl bg-brand px-6 py-10 text-on-brand sm:px-10">
			<h2 class="max-w-xl text-3xl font-bold tracking-tight">
				Your next application can be the prepared one.
			</h2>
			<p class="mt-3 max-w-lg text-sm leading-relaxed opacity-90">
				Start free. No card. Review every document before it leaves your hands.
			</p>
			<a
				href="/signup"
				class="mt-6 inline-flex h-11 items-center justify-center rounded-full bg-canvas px-5 text-sm font-semibold text-ink"
			>
				Start free
			</a>
		</div>
	</div>
</section>
