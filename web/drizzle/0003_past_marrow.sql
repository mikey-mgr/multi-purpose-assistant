CREATE TABLE "documents" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" text NOT NULL,
	"job_id" integer,
	"document_type" text NOT NULL,
	"rendercv_yaml" text,
	"content" text,
	"pdf_path" text,
	"docx_path" text,
	"prompt_name" text,
	"model" text,
	"tokens_used" integer DEFAULT 0,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "job_matches" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"job_id" integer NOT NULL,
	"user_id" text NOT NULL,
	"status" text DEFAULT 'matched' NOT NULL,
	"score" integer,
	"reason" text,
	"proceed" text,
	"apply_action" text,
	"apply_recipient" text,
	"apply_subject" text,
	"apply_body" text,
	"apply_url" text,
	"required_docs" text,
	"expiry_date" date,
	"merged_pdf" boolean DEFAULT false,
	"matched_by" text DEFAULT 'llm',
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "jobs" (
	"id" integer PRIMARY KEY NOT NULL,
	"public_id" uuid DEFAULT gen_random_uuid() NOT NULL,
	"source" text,
	"source_url" text,
	"title" text,
	"company" text,
	"location" text,
	"description" text,
	"job_type" text,
	"compensation" text,
	"date_posted" date,
	"expires" date,
	"category" text,
	"remote" text,
	"apply_instructions" text,
	"scraped_at" timestamp with time zone DEFAULT now() NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "jobs_public_id_unique" UNIQUE("public_id")
);
--> statement-breakpoint
ALTER TABLE "profiles" ADD COLUMN "legacy_user_id" text;--> statement-breakpoint
ALTER TABLE "documents" ADD CONSTRAINT "documents_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "documents" ADD CONSTRAINT "documents_job_id_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "job_matches" ADD CONSTRAINT "job_matches_job_id_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "job_matches" ADD CONSTRAINT "job_matches_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "documents_user_id_idx" ON "documents" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "documents_job_id_idx" ON "documents" USING btree ("job_id");--> statement-breakpoint
CREATE UNIQUE INDEX "job_matches_job_user_idx" ON "job_matches" USING btree ("job_id","user_id");--> statement-breakpoint
CREATE INDEX "job_matches_user_status_idx" ON "job_matches" USING btree ("user_id","status");--> statement-breakpoint
CREATE INDEX "jobs_date_posted_idx" ON "jobs" USING btree ("date_posted");--> statement-breakpoint
CREATE INDEX "jobs_category_idx" ON "jobs" USING btree ("category");--> statement-breakpoint
CREATE INDEX "jobs_company_idx" ON "jobs" USING btree ("company");