-- Jobs a user submitted themselves (e.g. forwarded on WhatsApp) are matched
-- only to that user. Scraped jobs keep a null owner and stay global.
ALTER TABLE "jobs" ADD COLUMN "owner_user_id" text;
