ALTER TABLE "application_kits" ADD COLUMN "metadata" jsonb;--> statement-breakpoint
ALTER TABLE "user_files" ADD COLUMN "purpose" text DEFAULT 'document' NOT NULL;