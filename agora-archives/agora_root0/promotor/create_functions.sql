DROP FUNCTION is_ordinary(integer);
DROP FUNCTION is_democratic(integer);
DROP FUNCTION is_parliamentary(integer);
DROP FUNCTION is_disinterested(integer);
DROP FUNCTION is_urgent(integer);
DROP FUNCTION is_sane(integer);
DROP FUNCTION is_contested(integer);
DROP FUNCTION is_nondistributable(integer);
DROP FUNCTION is_distributable(integer);
DROP FUNCTION is_distributed(integer);
DROP FUNCTION is_removed(integer);
DROP FUNCTION is_pos_advertised(integer);
DROP FUNCTION is_neg_advertised(integer);
DROP FUNCTION is_takeover(integer);

DROP FUNCTION proposal_cpid(integer, timestamp with time zone);
DROP FUNCTION proposal_cpid(integer, timestamp without time zone);
DROP FUNCTION status_overlay(integer, timestamp with time zone);
DROP FUNCTION status_overlay(integer, timestamp without time zone)s

DROP FUNCTION is_stalled(integer);
DROP FUNCTION is_stalled(integer, real);

--DROP FUNCTION check_proposal_flags(integer, real);

CREATE FUNCTION is_ordinary(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 1) = 1 AS is_ordinary'
  LANGUAGE 'SQL';

CREATE FUNCTION is_democratic(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 2) = 2 AS is_democratic'
  LANGUAGE 'SQL';

CREATE FUNCTION is_parliamentary(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 4) = 4 AS is_parliamentary'
  LANGUAGE 'SQL';

CREATE FUNCTION is_disinterested(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 8) = 8 AS is_disinterested'
  LANGUAGE 'SQL';

CREATE FUNCTION is_urgent(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 16) = 16 AS is_urgent'
  LANGUAGE 'SQL';

CREATE FUNCTION is_sane(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 32) = 32 AS is_sane'
  LANGUAGE 'SQL';

CREATE FUNCTION is_contested(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 64) = 64 AS is_contested'
  LANGUAGE 'SQL';

CREATE FUNCTION is_pos_advertised(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 128) = 128 AS is_pos_advertised'
  LANGUAGE 'SQL';

CREATE FUNCTION is_neg_advertised(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 256) = 256 AS is_neg_advertised'
  LANGUAGE 'SQL';

CREATE FUNCTION is_takeover(integer)
  RETURNS boolean
  AS 'SELECT ($1 & 512) = 512 AS is_takover'
  LANGUAGE 'SQL';

CREATE FUNCTION is_nondistributable(integer)
  RETURNS boolean
  AS 'SELECT $1 = 0 AS is_nondistributable'
  LANGUAGE 'SQL';

CREATE FUNCTION is_distributable(integer)
  RETURNS boolean
  AS 'SELECT $1 = 1 AS is_distributable'
  LANGUAGE 'SQL';

CREATE FUNCTION is_distributed(integer)
  RETURNS boolean
  AS 'SELECT $1 = 2 AS is_distributed'
  LANGUAGE 'SQL';

CREATE FUNCTION is_removed(integer)
  RETURNS boolean
  AS 'SELECT $1 = 3 AS is_removed'
  LANGUAGE 'SQL';


CREATE FUNCTION proposal_cpid(integer, timestamp with time zone)
  RETURNS text
  AS 'SELECT to_char($2, ''YY-'') || to_char($1, ''FM099'')
      AS proposal_cpid'
  LANGUAGE 'SQL';

CREATE FUNCTION proposal_cpid(integer, timestamp without time zone)
  RETURNS text
  AS 'SELECT to_char($2, ''YY-'') || to_char($1, ''FM099'')
      AS proposal_cpid'
  LANGUAGE 'SQL';

CREATE FUNCTION status_overlay(integer, timestamp with time zone)
  RETURNS integer
  AS 'SELECT
      CASE WHEN is_ordinary(p.flags) AND p.ai >= 2
           AND (p.status = 0 OR p.status = 1)
           THEN -1 ELSE p.status END AS status_overlay
      FROM proposal p WHERE p.pid = $1 AND p.idate = $2'
  LANGUAGE 'SQL';

CREATE FUNCTION status_overlay(integer, timestamp without time zone)
  RETURNS integer
  AS 'SELECT
      CASE WHEN is_ordinary(p.flags) AND p.ai >= 2
           AND (p.status = 0 OR p.status = 1)
           THEN -1 ELSE p.status END AS status_overlay
      FROM proposal p WHERE p.pid = $1 AND p.idate = $2'
  LANGUAGE 'SQL';

-- boolean is_stalled(integer status)
CREATE FUNCTION is_stalled(integer)
  RETURNS boolean
  AS 'SELECT $1 = -1 AS is_stalled'
  LANGUAGE 'SQL';

-- boolean is_stalled(integer flags, real ai)
CREATE FUNCTION is_stalled(integer, real)
  RETURNS boolean
  AS 'SELECT is_ordinary($1) AND $2 >= 2.0 AS is_stalled'
  LANGUAGE 'SQL';

/*
CREATE FUNCTION check_proposal_flags(integer, real)
  RETURNS boolean
  AS '
    DECLARE

      flags ALIAS FOR $1;
      ai ALIAS FOR $2;

    BEGIN

      IF is_ordinary(flags) THEN
        IF is_democratic(flags) OR is_parliamentary(flags) THEN
          RETURN false;
        END IF;
        IF ai >= 2 THEN
          RETURN false;
        END IF;
      ELSE
        IF is_democratic(flags) THEN
          IF is_parliamentary(flags) THEN
            RETURN false;
          END IF;
        ELSE
          IF NOT is_parliamentary(flags) THEN
            RETURN false;
          END IF;
        END IF;
      END IF;

      IF is_sane(flags) AND (is_disinterested(flags) OR NOT is_democratic(flags)) THEN
        RETURN false;
      END IF;

      IF is_urgent(flags) AND is_disinterested(flags) THEN
        RETURN false;
      END IF;

      IF is_contested(flags) AND NOT is_democratic(flags) THEN
        RETURN false;
      END IF;

    RETURN true;

    END;
  ' LANGUAGE 'plpgsql';
*/