ALTER TABLE "profiles" ADD COLUMN "resume_data" jsonb;--> statement-breakpoint
ALTER TABLE "profiles" ADD COLUMN "phone" text;--> statement-breakpoint
ALTER TABLE "profiles" ADD COLUMN "linkedin_url" text;--> statement-breakpoint
ALTER TABLE "profiles" ADD COLUMN "cv_template" text DEFAULT 'harvard' NOT NULL;