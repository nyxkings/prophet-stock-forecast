-- Additive outcome columns for stock_optimisation_store.
-- Safe to run once; all columns are nullable so existing rows remain valid.
-- Dashboard continues to work without these columns populated.

ALTER TABLE stock_optimisation_store
  ADD COLUMN IF NOT EXISTS prediction_target_date date,
  ADD COLUMN IF NOT EXISTS current_price double precision,
  ADD COLUMN IF NOT EXISTS actual_price double precision,
  ADD COLUMN IF NOT EXISTS actual_return double precision,
  ADD COLUMN IF NOT EXISTS price_error double precision,
  ADD COLUMN IF NOT EXISTS return_error double precision,
  ADD COLUMN IF NOT EXISTS scored_at timestamptz;
