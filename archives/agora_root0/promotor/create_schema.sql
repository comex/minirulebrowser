DROP VIEW proposal_pool;
DROP TABLE proposal_history;
DROP TABLE proposal_flags;
DROP TABLE proposal_status;
DROP TABLE proposal;

DROP SEQUENCE proposal_pid_seq;
DROP SEQUENCE proposal_dnum_seq;
DROP SEQUENCE proposal_history_hid_seq;

CREATE TABLE proposal (
  pid serial,
  title varchar(80) not null default 'Untitled',
  body text not null,
  proposer_id integer not null references player on delete no action on update cascade,
  sdate timestamp with time zone not null,
  status integer not null default 0 check (status >= 0 and status <= 3),
  ddate timestamp with time zone,
  ai real not null default 1,
  flags integer not null default 1 check (flags >= 0),
  dnum integer unique,
  idate timestamp with time zone not null,
  primary key (pid, idate),
  constraint no_chamber check (is_ordinary(flags) or is_democratic(flags) or
                               is_parliamentary(flags)),
  constraint bad_chamber check (not ((is_ordinary(flags) and is_democratic(flags))
    or (is_ordinary(flags) and is_parliamentary(flags))
    or (is_democratic(flags) and is_parliamentary(flags)))),
  constraint bad_sanity check ((not is_sane(flags))
    or ((not is_disinterested(flags)) and is_democratic(flags))),
  constraint bad_urgency check (not (is_urgent(flags) and
    is_disinterested(flags))),
  constraint bad_contested check ((not is_contested(flags))
    or is_democratic(flags)),
  constraint bad_advertising check (not (is_pos_advertised(flags) and
    is_neg_advertised(flags))),
  constraint bad_takeover check ((not is_takeover(flags)) or
    (is_democratic(flags) and is_sane(flags))),
  constraint bad_ddate check (is_distributed(status) != (ddate is null)) );

/* Proposal flags:         Distribution status:
 *   1 - Ordinary          0 - Undistributable
 *   2 - Democratic        1 - Distributable
 *   4 - Parliamentary     2 - Distributed
 *   8 - Disinterested     3 - Removed
 *  16 - Urgent
 *  32 - Sane
 *  64 - Contested
 * 128 - Positive Advertising
 * 256 - Negative Advertising
 * 512 - Takeover
*/


CREATE TABLE proposal_history (
  hid serial primary key,
  action text not null,
  adate timestamp with time zone not null,
  pid integer,
  pdate timestamp with time zone,
  in_reports boolean not null default true,
  constraint proposal_key foreign key (pid, pdate)
    references proposal (pid, idate) match full
    on delete cascade on update cascade);


CREATE TABLE proposal_flags (
  fid integer primary key,
  str varchar(20) not null,
  short char(1) unique );

CREATE TABLE proposal_status (
  sid integer primary key,
  str varchar(20) not null );

CREATE VIEW proposal_pool (num, title, body, proposer, ai, sdate, chamber,
  status, ddate, flags, oid, pid, cpid, dnum, statusid, idate, realstatusid)
  AS SELECT
    CASE WHEN is_distributed(p.status) THEN p.dnum::text
      ELSE proposal_cpid(p.pid, p.idate) END,
    p.title, p.body, e.name, p.ai, p.sdate, f.str, s.str,
    p.ddate, p.flags, p.oid, p.pid, proposal_cpid(p.pid,p.idate), p.dnum,
    s.sid, p.idate, p.status
    FROM proposal p, entity e, proposal_flags f, proposal_status s
    WHERE p.proposer_id = e.eid and f.fid <= 4 and p.flags & f.fid = f.fid
    AND status_overlay(p.pid, p.idate) = s.sid;

CREATE SEQUENCE proposal_dnum_seq;

GRANT SELECT ON proposal TO PUBLIC;
GRANT SELECT ON proposal_history TO PUBLIC;
GRANT SELECT ON proposal_flags TO PUBLIC;
GRANT SELECT ON proposal_status TO PUBLIC;
GRANT SELECT ON proposal_pool TO PUBLIC;