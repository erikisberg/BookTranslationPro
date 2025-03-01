-- Function to execute SQL from application code
-- WARNING: This is for setup/admin purposes only and should be used with caution
-- You should implement proper security checks around this
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  EXECUTE query;
  RETURN 'Query executed successfully';
EXCEPTION
  WHEN OTHERS THEN
    RETURN 'Error: ' || SQLERRM;
END;
$$;