#!/usr/bin/perl

# Syntax: set_distributable.pl -pnum <pnum> [-date <date> -comment <comment>]
#                              [-dnum <dnum>] [-disinterested]
#
# Comment variables:
# $# -> proposal number             $T -> proposal title
# $I -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($pnum, $date, $comment, $dnum, $disinterested, $st_from, $st_to);

$st_from = 0;
$st_to = 1;

while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-da/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
    elsif ($arg =~ m/^-dn/ && !index('-dnum', $arg)) {$dnum = shift @ARGV;}
#    elsif ($arg =~ m/^-di/ && !index('-disinterested', $arg)) {$disinterested = 1;}
    elsif ($arg =~ m/^-u/ && !index('-undistributable', $arg)) {$st_from = 1; $st_to = 0;}
    else {die "Unrecognized option: $arg";}
}

die "No pnum given" unless defined($pnum);
die "No date given" if defined($comment) && !defined($date);

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my $sth = $dbh->prepare("SELECT pid, idate, title, dnum FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
my $title = $$row[2];
$dnum = $$row[3] unless defined($dnum);
$sth->finish;


if ($disinterested) {
    $sth = $dbh->prepare("UPDATE proposal SET status = ?, dnum = ?, flags = flags | 8 WHERE pid = ? AND idate = ? AND status = ?")
        or die "Unable to prepare SQL query";
} else {
    $sth = $dbh->prepare("UPDATE proposal SET status = ?, dnum = ? WHERE pid = ? AND idate = ? AND status = ?")
        or die "Unable to prepare SQL query";
}
my $rv = $sth->execute($st_to, $dnum, $pid, $idate, $st_from);

if (!defined $rv || $rv < 1) {
    die "Failed to update proposal"; }


if (defined($comment)) {
    $sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, " .
                         "pid, pdate) VALUES (?, ?, ?, ?)")
        or die "Unable to prepare SQL query";

    $comment =~ s/\$\#/$pnum/g;
    $comment =~ s/\$T/$title/g;
    $comment =~ s/\$I/"$title" ($pnum)/g;

    $rv = $sth->execute($comment, $date, $pid, $idate);
    if (!defined $rv || $rv < 1) {
        die "Failed to insert proposal history comment"; }
}

if (defined($dnum)) {
    $sth = $dbh->prepare("SELECT CASE WHEN is_called THEN last_value " .
                         "ELSE last_value - increment_by END FROM proposal_dnum_seq")
        or die "Unable to prepare SQL query";
    $sth->execute or die "Failed to execute SQL query";

    $row = $sth->fetchrow_arrayref
        or die "Failed to retrieve dnum sequence value";
    my $last_dnum = $$row[0];
    $sth->finish;

    if ($dnum > $last_dnum) {
        $sth = $dbh->prepare("SELECT setval('proposal_dnum_seq', ?, 't')")
            or die "Failed to prepare SQL query";
        $sth->execute($dnum) or die "Failed to execute SQL query";
        $row = $sth->fetchrow_arrayref;
        if (!defined($row) || $$row[0] != $dnum) {
            die "Failed to reset dnum sequence";
        }
        $sth->finish;
    }
}

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
