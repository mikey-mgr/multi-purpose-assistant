import { sql } from 'drizzle-orm';
import {
	bigint,
	boolean,
	date,
	index,
	integer,
	jsonb,
	pgTable,
	primaryKey,
	text,
	timestamp,
	uniqueIndex,
	uuid
} from 'drizzle-orm/pg-core';

export const user = pgTable('user', {
	id: text('id').primaryKey(),
	name: text('name').notNull(),
	email: text('email').notNull().unique(),
	emailVerified: boolean('email_verified').notNull().default(false),
	image: text('image'),
	createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
	updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const session = pgTable(
	'session',
	{
		id: text('id').primaryKey(),
		expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
		token: text('token').notNull().unique(),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
		updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
		ipAddress: text('ip_address'),
		userAgent: text('user_agent'),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' })
	},
	(table) => [index('session_user_id_idx').on(table.userId)]
);

export const account = pgTable(
	'account',
	{
		id: text('id').primaryKey(),
		accountId: text('account_id').notNull(),
		providerId: text('provider_id').notNull(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		accessToken: text('access_token'),
		refreshToken: text('refresh_token'),
		idToken: text('id_token'),
		accessTokenExpiresAt: timestamp('access_token_expires_at', { withTimezone: true }),
		refreshTokenExpiresAt: timestamp('refresh_token_expires_at', { withTimezone: true }),
		scope: text('scope'),
		password: text('password'),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
		updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('account_user_id_idx').on(table.userId)]
);

export const verification = pgTable(
	'verification',
	{
		id: text('id').primaryKey(),
		identifier: text('identifier').notNull(),
		value: text('value').notNull(),
		expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
		updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('verification_identifier_idx').on(table.identifier)]
);

export const rateLimit = pgTable(
	'rate_limit',
	{
		id: text('id').primaryKey(),
		key: text('key').notNull(),
		count: integer('count').notNull().default(0),
		lastRequest: bigint('last_request', { mode: 'number' }).notNull().default(0)
	},
	(table) => [uniqueIndex('rate_limit_key_idx').on(table.key)]
);

export const profiles = pgTable('profiles', {
	userId: text('user_id')
		.primaryKey()
		.references(() => user.id, { onDelete: 'cascade' }),
	headline: text('headline'),
	location: text('location'),
	yearsExperience: integer('years_experience').notNull().default(0),
	targetFamilies: text('target_families')
		.array()
		.notNull()
		.default(sql`'{}'::text[]`),
	matchMode: text('match_mode').notNull().default('balanced'),
	onboardingCompleted: boolean('onboarding_completed').notNull().default(false),
	legacyUserId: text('legacy_user_id'),
	matchSince: timestamp('match_since', { withTimezone: true }),
	createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
	updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const deviceProfiles = pgTable(
	'device_profiles',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		score: integer('score').notNull(),
		bucket: text('bucket').notNull(),
		country: text('country'),
		currency: text('currency').notNull().default('USD'),
		signalsHash: text('signals_hash').notNull(),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('device_profiles_user_id_idx').on(table.userId)]
);

export const pricingVariants = pgTable('pricing_variants', {
	userId: text('user_id')
		.primaryKey()
		.references(() => user.id, { onDelete: 'cascade' }),
	experiment: text('experiment').notNull().default('price_v1'),
	variant: text('variant').notNull(),
	pricePro: integer('price_pro').notNull(),
	priceByok: integer('price_byok').notNull(),
	currency: text('currency').notNull().default('USD'),
	assignedAt: timestamp('assigned_at', { withTimezone: true }).notNull().defaultNow()
});

export const apiRateLimits = pgTable(
	'api_rate_limits',
	{
		key: text('key').notNull(),
		windowStart: timestamp('window_start', { withTimezone: true }).notNull(),
		count: integer('count').notNull().default(0)
	},
	(table) => [primaryKey({ columns: [table.key, table.windowStart] })]
);

export type KitAttachment = {
	name: string;
	mime: string;
	contentBase64: string;
};

export const jobs = pgTable(
	'jobs',
	{
		id: integer('id').primaryKey(),
		publicId: uuid('public_id').notNull().defaultRandom().unique(),
		source: text('source'),
		sourceUrl: text('source_url'),
		title: text('title'),
		company: text('company'),
		location: text('location'),
		description: text('description'),
		jobType: text('job_type'),
		compensation: text('compensation'),
		datePosted: date('date_posted'),
		expires: date('expires'),
		category: text('category'),
		remote: text('remote'),
		applyInstructions: text('apply_instructions'),
		scrapedAt: timestamp('scraped_at', { withTimezone: true }).notNull().defaultNow(),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [
		index('jobs_date_posted_idx').on(table.datePosted),
		index('jobs_category_idx').on(table.category),
		index('jobs_company_idx').on(table.company)
	]
);

export const jobMatches = pgTable(
	'job_matches',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		jobId: integer('job_id')
			.notNull()
			.references(() => jobs.id, { onDelete: 'cascade' }),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		status: text('status').notNull().default('matched'),
		score: integer('score'),
		reason: text('reason'),
		proceed: text('proceed'),
		applyAction: text('apply_action'),
		applyRecipient: text('apply_recipient'),
		applySubject: text('apply_subject'),
		applyBody: text('apply_body'),
		applyUrl: text('apply_url'),
		requiredDocs: text('required_docs'),
		expiryDate: date('expiry_date'),
		mergedPdf: boolean('merged_pdf').default(false),
		matchedBy: text('matched_by').default('llm'),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [
		uniqueIndex('job_matches_job_user_idx').on(table.jobId, table.userId),
		index('job_matches_user_status_idx').on(table.userId, table.status)
	]
);

export const documents = pgTable(
	'documents',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		jobId: integer('job_id').references(() => jobs.id, { onDelete: 'set null' }),
		documentType: text('document_type').notNull(),
		rendercvYaml: text('rendercv_yaml'),
		content: text('content'),
		pdfPath: text('pdf_path'),
		docxPath: text('docx_path'),
		promptName: text('prompt_name'),
		model: text('model'),
		tokensUsed: integer('tokens_used').default(0),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [
		index('documents_user_id_idx').on(table.userId),
		index('documents_job_id_idx').on(table.jobId)
	]
);

export const oauthAccounts = pgTable(
	'oauth_accounts',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		provider: text('provider').notNull(),
		providerAccountId: text('provider_account_id'),
		email: text('email'),
		scope: text('scope'),
		encryptedRefreshToken: text('encrypted_refresh_token').notNull(),
		iv: text('iv').notNull(),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
		updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [uniqueIndex('oauth_accounts_user_provider_idx').on(table.userId, table.provider)]
);

export const oauthStates = pgTable('oauth_states', {
	id: text('id').primaryKey(),
	userId: text('user_id')
		.notNull()
		.references(() => user.id, { onDelete: 'cascade' }),
	provider: text('provider').notNull(),
	expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
	createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
});

export const applicationKits = pgTable(
	'application_kits',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		jobId: text('job_id'),
		jobTitle: text('job_title'),
		company: text('company'),
		recipient: text('recipient').notNull(),
		subject: text('subject').notNull(),
		body: text('body').notNull(),
		attachments: jsonb('attachments')
			.$type<KitAttachment[]>()
			.notNull()
			.default(sql`'[]'::jsonb`),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('application_kits_user_id_idx').on(table.userId)]
);

export const payments = pgTable(
	'payments',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		reference: text('reference').notNull().unique(),
		plan: text('plan').notNull(),
		amountCents: integer('amount_cents').notNull(),
		currency: text('currency').notNull().default('USD'),
		status: text('status').notNull().default('created'),
		paynowReference: text('paynow_reference'),
		pollUrl: text('poll_url'),
		raw: jsonb('raw'),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
		updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
		paidAt: timestamp('paid_at', { withTimezone: true })
	},
	(table) => [index('payments_user_id_idx').on(table.userId)]
);

export const subscriptions = pgTable('subscriptions', {
	userId: text('user_id')
		.primaryKey()
		.references(() => user.id, { onDelete: 'cascade' }),
	plan: text('plan').notNull().default('free'),
	status: text('status').notNull().default('active'),
	currentPeriodEnd: timestamp('current_period_end', { withTimezone: true }),
	updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const whatsappPilot = pgTable(
	'whatsapp_pilot',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id')
			.notNull()
			.unique()
			.references(() => user.id, { onDelete: 'cascade' }),
		phone: text('phone').notNull().unique(),
		slot: integer('slot').unique(),
		status: text('status').notNull().default('active'),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('whatsapp_pilot_phone_idx').on(table.phone)]
);

export const whatsappMessages = pgTable(
	'whatsapp_messages',
	{
		id: uuid('id').primaryKey().defaultRandom(),
		userId: text('user_id').references(() => user.id, { onDelete: 'set null' }),
		phone: text('phone').notNull(),
		direction: text('direction').notNull().default('inbound'),
		body: text('body'),
		raw: jsonb('raw'),
		createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
	},
	(table) => [index('whatsapp_messages_phone_idx').on(table.phone)]
);
