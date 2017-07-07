#!/usr/bin/perl
#
# USAGE: gen_pool_report.pl [-period <period>]

use strict;
use DBI;
use POSIX qw(strftime);

$ENV{PGTZ} = "GMT";

my $period = '1 month';

while (defined(my $arg = shift @ARGV)) {
    if ($arg =~ m/^-p/ && !index('-period', $arg)) {$period = shift @ARGV;}
    else {die "Unknown argument $arg";}
}

my $report_time = strftime "%B %d, %Y", gmtime;
my $last_report_time;
my $last_ratify_time;
my $dbname = "agora";
my $username = "agora";
my $dbh;
my $sth;
my $sth2;
my $row;
my $title;
my $body;
my $status;
my @action;
my $col;
my $word;

print "Agora Nomic\nPromotor's Proposal Pool Report\n$report_time\n\n\n",
  "View the PHP version of the Proposal Pool at\n",
  "http://www.periware.org/agora/pool.php\n\n\n";

$dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "")
    or die "Unable to connect to database";

$sth = $dbh->prepare("SELECT max(published) FROM report " .
                     "WHERE type & 1 = 1 AND NOT correction")
    or die "Unable to prepare SQL query";

$sth->execute or die "Unable to execute SQL query";

$row = $sth->fetchrow_arrayref;

if (defined($row)) {
    $last_report_time = $$row[0]; }
else {
    $last_report_time = '-infinity'; }

$sth = $dbh->prepare("SELECT max(published) FROM report " .
                     "WHERE type & 1 = 1 AND NOT correction " .
                     "AND ratified IS NOT NULL")
    or die "Unable to prepare SQL query";

$sth->execute or die "Unable to execute SQL query";

$row = $sth->fetchrow_arrayref;

if (defined($row)) {
    $last_ratify_time = $$row[0]; }
else {
    $last_ratify_time = '-infinity'; }

if ($last_report_time ne '-infinity') {
    print "Time of last report:  $last_report_time\n"; }

if ($last_ratify_time ne '-infinity') {
    print "Report last ratified: $last_ratify_time\n"; }

print "\n\n";

$sth = $dbh->prepare("SELECT num, title, proposer, ai, " .
                     "to_char(sdate, 'DDMonYY'), flags " .
                     "FROM proposal_pool WHERE is_distributable(statusid) " .
                     "ORDER BY num")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

$sth2 = $dbh->prepare("SELECT short FROM proposal_flags " .
                      "WHERE ? & fid = fid ORDER BY fid")
    or die "Unable to prepare sql query";


print
  "----------------------------------------------------------------------",
  "\n\nProposal Pool\n\n\n",
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

print "\n\n",
  "O: Ordinary D: Democratic\n",
  "*: See proposal below for exact AI\n\n\n",
#  "Note: For undistributed proposals, AI is projected, not actual.\n\n\n",
  "----------------------------------------------------------------------\n",
  "\n\nBudget Items\n------------\n\nPer-Player Proposal Limit: 4\n",
  "\n\nRecent events\n-------------\n\n\n";

$sth = $dbh->prepare("SELECT agora_date(adate), action " .
                     "FROM proposal_history " .
                     "WHERE adate + ? >= now() " .
                     "AND adate < '$last_report_time' " .
                     "AND in_reports " .
                     "ORDER BY adate, hid")
    or die "Unable to prepare sql query";

$sth->execute($period) or die "Unable to execute SQL query";

while (defined($row = $sth->fetchrow_arrayref)) {
    print "Date: $$row[0]";

    @action = split / +/, $$row[1];
    $col = 71;
    foreach $word (@action) {
        if (length($word) + $col > 70) {
            print "\n      $word";
            $col = length($word) + 6; }
        else {
            print " $word";
            $col += length($word) + 1; } }
    print "\n\n\n"; }

print "------------------------- TIME OF LAST REPORT ------------------------\n\n\n";

$sth = $dbh->prepare("SELECT agora_date(adate), action " .
                     "FROM proposal_history " .
                     "WHERE adate >= '$last_report_time' " .
                     "AND in_reports " .
                     "ORDER BY adate, hid")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute SQL query";

while (defined($row = $sth->fetchrow_arrayref)) {
    print "Date: $$row[0]";

    @action = split / +/, $$row[1];
    $col = 71;
    foreach $word (@action) {
        if (length($word) + $col > 70) {
            print "\n      $word";
            $col = length($word) + 6; }
        else {
            print " $word";
            $col += length($word) + 1; } }
    print "\n\n\n"; }

print "======================================================================\n\n",
  "Text of Proposals in the Pool (not a distribution)\n\n\n",
  "----------------------------------------------------------------------\n";

$sth = $dbh->prepare("SELECT num, proposer, ai, title, body, flags, status " .
                     "FROM proposal_pool " .
                     "WHERE is_distributable(statusid) " .
                     "OR is_stalled(statusid) " .
                     "OR is_nondistributable(statusid) " .
                     "ORDER BY statusid DESC, num")
    or die "Unable to prepare sql query";

$sth->execute or die "Unable to execute sql query";

$sth2 = $dbh->prepare("SELECT str FROM proposal_flags " .
                      "WHERE ? & fid = fid ORDER BY fid" )
    or die "Unable to prepare sql query";

while (defined($row = $sth->fetchrow_arrayref)) {
    print "\n\nProposal $$row[0] by $$row[1], AI=$$row[2]";

    $title = $$row[3];
    $body = $$row[4];
    $status = $$row[6];

    $sth2->execute($$row[5]) or die "Unable to execute sql query";
    while (defined($row = $sth2->fetchrow_arrayref)) {
        print ", $$row[0]"; }
    print ", $status\n$title\n\n\n";

    if(  $body =~ m/[~ ]+/ ) {
        print "$body\n\n\n"; }

    print "----------------------------------------------------------------------\n";
}
    

$dbh->disconnect;
