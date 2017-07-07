#!/usr/bin/perl

# Syntax: set_dnum.pl -pnum <pnum> [-dnum <dnum>]
#
# If dnum is unspecified, the next unused dnum is used.


use strict;
use DBI;

my ($pnum, $dnum);

while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-d/ && !index('-dnum', $arg)) {$dnum = shift @ARGV;}
    else {die "Unrecognized option: $arg";}
}

die "No pnum given" unless defined($pnum);

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my ($sth, $row, $rv);

$sth = $dbh->prepare("SELECT pid, idate FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
$sth->finish;


if (defined($dnum)) {
    $sth = $dbh->prepare("SELECT CASE WHEN is_called THEN last_value " .
                         "ELSE last_value - increment_by END FROM proposal_dnum_seq")
        or die "Unable to prepare SQL query";

    $sth->execute or die "Unable to execute SQL query";

    $row = $sth->fetchrow_arrayref;
    if (!defined($row)) {
        die "Unable to fetch dnum sequence information"; }

    my $last_dnum = $$row[0];
    $sth->finish;


    $sth = $dbh->prepare("UPDATE proposal SET dnum = ? WHERE pid = ? AND idate = ? AND (status = 0 OR status = 1)")
        or die "Unable to prepare SQL query";
    $rv = $sth->execute($dnum, $pid, $idate);

    if (!defined $rv || $rv < 1) {
        die "Failed to update proposal"; }


    if ($dnum > $last_dnum) {
        $sth = $dbh->prepare("SELECT setval('proposal_dnum_seq', ?, 't')")
            or die "Unable to prepare SQL query";
        $sth->execute($dnum) or die "Failed to execute SQL query";
        $row = $sth->fetchrow_arrayref;
        if (!defined($row) || $$row[0] != $dnum) {
            die "Failed to reset dnum sequence";
        }
        $sth->finish;
    }

} else {
    $sth = $dbh->prepare("UPDATE proposal SET dnum = nextval('proposal_dnum_seq') WHERE pid = ? AND idate = ? AND (status = 0 OR status = 1)")
        or die "Unable to prepare SQL query";
    $rv = $sth->execute($pid, $idate);

    if (!defined $rv || $rv < 1) {
        die "Failed to update proposal"; }
}

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
