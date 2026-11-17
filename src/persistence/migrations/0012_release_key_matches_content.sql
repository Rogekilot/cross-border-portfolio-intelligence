-- CP2 fix round, migration 12 (review finding C2-6): a market-data release row must be the release its content says.
-- 0001-0011 are frozen. This migration adds one CHECK and changes nothing else.
--
-- THE GAP. `md_release.release_id` is the SHA-256 of the canonical release content, and `release_content` holds that
-- content, but nothing tied the two together in the database: a row keyed `999...9` could hold another release's
-- content, and a reader asking for `999...9` would get a port whose `release_id()` is a different one (a Computation
-- Manifest would then cite a release other than the rows it read, P9). `read_release` now checks the same equality
-- and that `md_release_file` lists exactly the release's files; this CHECK stops a new row from being written wrong.
--
-- NOT VALID, deliberately (the R4-1 lesson of 0008): the constraint applies to every NEW row and is not re-checked
-- against rows already stored, so upgrading a database that holds a pre-0012 release can never fail on this file.
-- The read-side check covers those rows. The table refuses UPDATE for every role, so a stored row is never edited.
--
-- `release_content` is the canonical release JSON written by `MarketDataRelease.to_json()`, which carries its own
-- `release_id` and `convention_set_id` fields.

ALTER TABLE md_release
    ADD CONSTRAINT md_release_key_matches_content CHECK (
        release_content ->> 'release_id' = release_id
        AND release_content ->> 'convention_set_id' = convention_set_id
    ) NOT VALID;
