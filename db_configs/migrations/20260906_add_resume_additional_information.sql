-- Stores candidate-controlled CV footer information on each immutable resume version.
ALTER TABLE resumes
    ADD COLUMN IF NOT EXISTS additional_information JSONB NOT NULL DEFAULT '{}'::jsonb;
