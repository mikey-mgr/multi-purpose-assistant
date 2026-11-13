CREATE TABLE "agent_tasks" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"kind" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"payload" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"result" jsonb,
	"agent_id" uuid,
	"attempts" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"claimed_at" timestamp with time zone,
	"lease_expires_at" timestamp with time zone,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "agents" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"kind" text DEFAULT 'scraper' NOT NULL,
	"key_hash" text NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	"last_seen_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"revoked_at" timestamp with time zone,
	CONSTRAINT "agents_key_hash_unique" UNIQUE("key_hash")
);
--> statement-breakpoint
ALTER TABLE "agent_tasks" ADD CONSTRAINT "agent_tasks_agent_id_agents_id_fk" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "agent_tasks_kind_status_idx" ON "agent_tasks" USING btree ("kind","status");--> statement-breakpoint
CREATE INDEX "agent_tasks_agent_id_idx" ON "agent_tasks" USING btree ("agent_id");--> statement-breakpoint
CREATE SEQUENCE IF NOT EXISTS "jobs_id_seq";
ALTER TABLE "jobs" ALTER COLUMN "id" SET DEFAULT nextval('jobs_id_seq');
SELECT setval('jobs_id_seq', COALESCE((SELECT MAX("id") FROM "jobs"), 0) + 1, false);
--> statement-breakpoint
CREATE UNIQUE INDEX "jobs_source_url_idx" ON "jobs" USING btree ("source_url");