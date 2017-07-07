DROP VIEW entity_short;

DROP TABLE player;
DROP TABLE entity;
DROP TABLE report;

DROP SEQUENCE entity_eid_seq;
DROP SEQUENCE report_rid_seq;

CREATE TABLE entity (
  eid serial primary key,
  name varchar(80) not null,
  short varchar(20) );

CREATE VIEW entity_short (eid, name)
  AS SELECT eid, short FROM entity WHERE short IS NOT NULL
    UNION SELECT eid, name FROM entity WHERE short IS NULL;

CREATE TABLE player (
  pid integer primary key references entity,
  current boolean not null default true );

CREATE TABLE report (
  rid serial primary key,
  type integer not null,
  published timestamp with time zone not null,
  ratified timestamp with time zone,
  body text not null,
  correction boolean not null default false );

/* Report type flags:
 * 1 - Promotor pool report
 * 2 - Promotor papyrus report
 * 4 - ADoP report
*/