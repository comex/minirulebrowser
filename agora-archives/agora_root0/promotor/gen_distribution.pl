#!/usr/bin/perl
#
# USAGE: gen_distribution.pl [-noassign]

use strict;
use DBI;
use POSIX qw(strftime);

$ENV{PGTZ} = "GMT";

my $noassign; # if set, only distribute proposals with dnums already assigned

while (defined(my $arg = shift @ARGV)) {
    if ($arg =~ m/^-n/ && !index('-noassign', $arg)) {$noassign = 1;}
    else {die "Unknown argument $arg";}
}

my $report_time = strftime "%B %d, %Y", gmtime;
my $dbname = "agora";
my $username = "agora";
my $dbh;
my $sth;
my $sth2;
my $row;
my $title;
my $body;
my $dnum_min;
my $dnum_max;
my $dnum_range;

$dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "")
    or die "Unable to connect to database";

unless ($noassign) {
    $sth = $dbh->prepare("UPDATE proposal " .
                         "SET dnum = nextval('proposal_dnum_seq') " .
                         "WHERE is_distributable(status) AND dnum IS NULL " .
                         "AND NOT is_stalled(flags, ai)")
        or die "Unable to prepare sql query";

    if (!defined($sth->execute)) {
        die "Unable to execute sql query"; }
}

$sth = $dbh->prepare("SELECT min(dnum), max(dnum) FROM proposal " .
                     "WHERE is_distributable(status) AND dnum IS NOT NULL " .
                     "AND NOT is_stalled(flags, ai)")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

if (!defined($row = $sth->fetchrow_arrayref)) {
    die "Unable to fetch dnum range"; }

($dnum_min, $dnum_max) = @$row;
if ($dnum_min == $dnum_max) {
    $dnum_range = "Proposal $dnum_min"; }
else {
    $dnum_range = "Proposals $dnum_min-$dnum_max"; }

print "Agora Nomic\nDistribution of $dnum_range\n$report_time\n\n\n",
  "----------------------------------------------------------------------\n",
  "No.    | Title                       | By        | AI | Date    | Flag\n",
  "       |                             |           |    |         |\n";

$sth = $dbh->prepare("SELECT dnum, title, proposer, ai, " .
                     "to_char(sdate, 'DDMonYY'), flags " .
                     "FROM proposal_pool " .
                     "WHERE is_distributable(statusid) " .
                     "AND dnum IS NOT NULL " .
                     "ORDER BY dnum")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

$sth2 = $dbh->prepare("SELECT short FROM proposal_flags " .
                      "WHERE ? & fid = fid ORDER BY fid")
    or die "Unable to prepare sql query";

while (defined($row = $sth->fetchrow_arrayref)) {

    $title = $$row[1];
    if (length $title > 27) {
        $title = substr($title, 0, 24) . '...'; }

    my $flag_ai = ' ';
    if ($$row[3] != int($$row[3])) {
        $flag_ai = '*';
    }

    printf ("%-6d | %-27.27s | %-9.9s | %1.0f%1s | %7.7s | ",
            ($$row[0], $title, @$row[2..3], $flag_ai, $$row[4]));
    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print $$row[0]; }

    print "\n"; }

print "\n\n",
  "O: Ordinary D: Democratic\n",
  "* See proposal below for exact AI\n",
  "----------------------------------------------------------------------\n";

$sth = $dbh->prepare("SELECT dnum, proposer, ai, " .
                     "title, body, flags " .
                     "FROM proposal_pool " .
                     "WHERE is_distributable(statusid) " .
                     "AND dnum IS NOT NULL " .
                     "ORDER BY dnum")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

$sth2 = $dbh->prepare("SELECT str FROM proposal_flags " .
                      "WHERE ? & fid = fid ORDER BY fid" )
    or die "Unable to prepare sql query";

while (defined($row = $sth->fetchrow_arrayref)) {
    print "\n\nProposal $$row[0] by $$row[1], AI=$$row[2]";

    $title = $$row[3];
    $body = $$row[4];

    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print ", $$row[0]"; }
    print "\n$title\n\n\n";

    if(  $body =~ m/[~ ]+/ ) {
        print "$body\n\n\n"; }

    print "----------------------------------------------------------------------\n";
}
    

$dbh->disconnect;
