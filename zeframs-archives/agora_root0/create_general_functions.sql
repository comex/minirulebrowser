DROP FUNCTION agora_date(timestamp without time zone);
DROP FUNCTION agora_date(timestamp with time zone);

CREATE FUNCTION agora_date(timestamp without time zone)
RETURNS text
AS 'SELECT to_char($1, ''Dy, YYYY-MM-DD HH24:MI:SS''::text) AS agora_date'
LANGUAGE 'SQL';

CREATE FUNCTION agora_date(timestamp with time zone)
RETURNS text
AS 'SELECT to_char($1, ''Dy, YYYY-MM-DD HH24:MI:SS''::text) AS agora_date'
LANGUAGE 'SQL';