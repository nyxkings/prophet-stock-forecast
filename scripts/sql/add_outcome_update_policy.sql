-- Allow the service role to UPDATE outcome columns when scoring predictions.
-- Run once after add_outcome_columns.sql if score-outcomes fails with RLS/permission errors.
-- If the policy already exists, drop it first or ignore the duplicate error.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'stock_optimisation_store'
      AND policyname = 'Enable update access for service role'
  ) THEN
    CREATE POLICY "Enable update access for service role"
      ON stock_optimisation_store
      FOR UPDATE
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;
