type Env = {
	MATCHING_SCHEDULER_URL: string;
	SCRAPE_URL: string;
	GENERATION_URL: string;
	SCHEDULER_SECRET: string;
	AGENT_BOOTSTRAP_SECRET: string;
	SCRAPE_SITES: string;
	SCRAPE_MAX_JOBS: string;
};

export default {
	async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
		const tasks: Promise<Response>[] = [];

		// 05,08,11,14,17 UTC = 07:00, 10:00, 13:00, 16:00, 19:00 Africa/Harare (UTC+2).
		if (controller.cron === '0 5,8,11,14,17 * * *') {
			const sites = (
				env.SCRAPE_SITES || 'applynow,vacancymail,iharare,vacancybox,greenhouse,ashby'
			)
				.split(',')
				.map((site) => site.trim())
				.filter(Boolean);
			const maxJobs = Number(env.SCRAPE_MAX_JOBS || '25');
			for (const site of sites) {
				tasks.push(
					fetch(env.SCRAPE_URL, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							'x-agent-bootstrap-secret': env.AGENT_BOOTSTRAP_SECRET
						},
						body: JSON.stringify({
							site_names: [site],
							max_pages: 1,
							max_jobs: maxJobs
						})
					})
				);
			}
		}

		tasks.push(
			fetch(env.GENERATION_URL, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'x-scheduler-secret': env.SCHEDULER_SECRET
				},
				body: JSON.stringify({ auto_send: true })
			})
		);

		tasks.push(
			fetch(env.MATCHING_SCHEDULER_URL, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'x-scheduler-secret': env.SCHEDULER_SECRET
				},
				body: '{}'
			})
		);

		ctx.waitUntil(
			Promise.allSettled(tasks).then((results) => {
				for (const result of results) {
					if (result.status === 'rejected' || !result.value.ok) {
						console.error('Scheduled task failed', result);
					}
				}
			})
		);
	}
};
