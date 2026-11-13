-- Bind agents to the account they act for, so an agent can only claim and
-- send its own user's applications.
ALTER TABLE "agents" ADD COLUMN "user_id" text;--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade;
