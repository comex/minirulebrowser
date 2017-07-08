#!/usr/bin/perl

# Syntax: set_ai.pl -pnum <pnum> -ai <ai>
#                   [-date <date> [-comment <comment>]]
#
# Comment variables:
# $P -> proposer's name     $# -> proposal number
# $T -> proposal title      $I -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($pnum, $date, $ai, $comment);

while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-d/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-a/ && !index('-ai', $arg)) {$ai = shift @ARGV;}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
    else {die "Unrecognized option: $arg";}
}

die "No pnum given" unless defined($pnum);
die "No date given" if defined($comment) && !defined($date);

if (defined($date) && !defined($comment)) {
    $comment = '$P requests an AI of ' . $ai . ' for $I';
}

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my $sth = $dbh->prepare("SELECT pid, idate, title, proposer FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
my $title = $$row[2];
my $proposer = $$row[3];
$sth->finish;


my $rv;

$sth = $dbh->prepare("UPDATE proposal SET ai = ? WHERE pid = ? AND idate = ? AND (status = 0 OR status = 1)")
    or die "Unable to prepare SQL query";
$rv = $sth->execute($ai, $pid, $idate);

if (!defined $rv || $rv < 1) {
    die "Failed to update proposal"; }


if (defined($comment)) {
    $sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, " .
                         "pid, pdate) VALUES (?, ?, ?, ?)")
        or die "Unable to prepare SQL query";

    $comment =~ s/\$P/$proposer/g;
    $comment =~ s/\$\#/$pnum/g;
    $comment =~ s/\$T/$title/g;
    $comment =~ s/\$I/"$title" ($pnum)/g;

    $rv = $sth->execute($comment, $date, $pid, $idate);
    if (!defined $rv || $rv < 1) {
        die "Failed to insert proposal history comment"; }
}

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
