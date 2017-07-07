#!/usr/bin/perl

# Syntax: discard_proposal.pl -pnum <pnum> -date <date> -comment <comment>
#
# Comment variables:
# $# -> proposal number          $T -> proposal title
# $I -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($pnum, $date, $comment);

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-d/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
    else {die "Unrecognized argument: $arg";}
}

die "No pnum given" unless defined $pnum;
die "No date given" unless defined $date;
die "No comment given" unless defined $comment;

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

# Fetch proposal information from dnum or cpid
my $sth = $dbh->prepare("SELECT pid, idate, title, realstatusid FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
my $title = $$row[2];
my $status = $$row[3];
$sth->finish;

if ($status != 0 && $status != 1) {
    die "Cannot discard proposal $pnum";
}


# Mark proposal discarded
$sth = $dbh->prepare("UPDATE proposal SET status = 3 WHERE pid = ? AND idate = ?")
    or die "Unable to prepare SQL query";
my $rv = $sth->execute($pid, $idate);

if (!defined $rv || $rv < 1) {
    die "Failed to update proposal"; }


# Perform variable substitution
$comment =~ s/\$\#/$pnum/g;
$comment =~ s/\$T/$title/g;
$comment =~ s/\$I/"$title" ($pnum)/g;

# Add history item
$sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, " .
                     "pid, pdate) VALUES (?, ?, ?, ?)")
    or die "Unable to prepare SQL query";

$rv = $sth->execute($comment, $date, $pid, $idate);
if (!defined $rv || $rv < 1) {
    die "Failed to insert proposal history comment"; }

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
