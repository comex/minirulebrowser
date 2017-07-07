#!/usr/bin/perl

use strict;
use DBI;

$ENV{PGTZ} = "GMT";

my $dbname = "agora";
my $username = "agora";
my $dbh;
my $sth;
my $sth2;
my $row;
my $title;

$dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "")
    or die "Unable to connect to database";

$sth = $dbh->prepare("SELECT num, title, proposer, ai, " .
                     "to_char(sdate, 'DDMonYY'), flags " .
                     "FROM proposal_pool WHERE is_distributable(statusid) " .
                     "ORDER BY num ASC")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

$sth2 = $dbh->prepare("SELECT short FROM proposal_flags " .
                      "WHERE ? & fid = fid ORDER BY fid")
    or die "Unable to prepare sql query";


print
  "No.    | Title                       | By        | AI | Date    | Flag\n",
  "       |                             |           |    |         |\n",
  "-------|---Distributable Proposals---|-----------|----|---------|-----\n",
  "       |                             |           |    |         |\n";

while (defined($row = $sth->fetchrow_arrayref)) {

    $title = $$row[1];
    if (length $title > 27) {
        $title = substr($title, 0, 24) . '...'; }

    my $flag_ai = ' ';
    if ($$row[3] != int($$row[3])) {
        $flag_ai = '*';
    }

    printf ("%6.6s | %-27.27s | %-9.9s | %1.0f%1s | %7.7s | ",
            ($$row[0], $title, @$row[2..3], $flag_ai, $$row[4]));
    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print $$row[0]; }

    print "\n"; }

print "       |                             |           |    |         |\n",
  "-------|-Non-distributable Proposals-|-----------|----|---------|-----\n",
  "       |                             |           |    |         |\n";

$sth = $dbh->prepare("SELECT num, title, proposer, ai, " .
                     "to_char(sdate, 'DDMonYY'), flags " .
                     "FROM proposal_pool WHERE is_nondistributable(statusid) " .
                     "ORDER BY num")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

while (defined($row = $sth->fetchrow_arrayref)) {

    $title = $$row[1];
    if (length $title > 27) {
        $title = substr($title, 0, 24) . '...'; }

    my $flag_ai = ' ';
    if ($$row[3] != int($$row[3])) {
        $flag_ai = '*';
    }

    printf ("%6.6s | %-27.27s | %-9.9s | %1.0f%1s | %7.7s | ",
            ($$row[0], $title, @$row[2..3], $flag_ai, $$row[4]));
    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print $$row[0]; }

    print "\n"; }

print "       |                             |           |    |         |\n",
  "-------|------Stalled Proposals------|-----------|----|---------|-----\n",
  "       |                             |           |    |         |\n";

$sth = $dbh->prepare("SELECT num, title, proposer, ai, " .
                     "to_char(sdate, 'DDMonYY'), flags " .
                     "FROM proposal_pool WHERE is_stalled(statusid) " .
                     "ORDER BY num")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

while (defined($row = $sth->fetchrow_arrayref)) {

    $title = $$row[1];
    if (length $title > 27) {
        $title = substr($title, 0, 24) . '...'; }

    my $flag_ai = ' ';
    if ($$row[3] != int($$row[3])) {
        $flag_ai = '*';
    }

    printf ("%6.6s | %-27.27s | %-9.9s | %1.0f%1s | %7.7s | ",
            ($$row[0], $title, @$row[2..3], $flag_ai, $$row[4]));
    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print $$row[0]; }

    print "\n"; }

$dbh->disconnect;
