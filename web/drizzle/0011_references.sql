-- References saved on the profile and whether they appear on generated CVs.
ALTER TABLE "profiles" ADD COLUMN "references" jsonb DEFAULT '[]'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "profiles" ADD COLUMN "references_enabled" boolean DEFAULT false NOT NULL;
