-- CP2 final check, migration 13 (review finding C2-16; market-data/1.7 Test V0-FX). 0001-0012 are frozen.
--
-- A series NOT admitted (Ruling 3.1 consequences) was keyed by (listing, file). Test V0-FX excludes an FX series: one
-- currency of one FX file. Such an exclusion has no listing, so `listing_id` becomes nullable and a `currency` column names
-- the series; exactly one of the two is set. The table stays append-only and sealed with its release (migration 0011:
-- the triggers do not depend on these columns), existing rows keep (listing_id set, currency NULL) and satisfy the new CHECK,
-- and no grant changes (the application role already holds SELECT on this table).

ALTER TABLE md_series_exclusion ALTER COLUMN listing_id DROP NOT NULL;
ALTER TABLE md_series_exclusion ADD COLUMN currency text NULL CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$');
ALTER TABLE md_series_exclusion ADD CONSTRAINT md_series_exclusion_subject CHECK (
    (listing_id IS NOT NULL AND currency IS NULL) OR (listing_id IS NULL AND currency IS NOT NULL));
