#!/usr/bin/perl
#
# USAGE: cat_proposal.pl -pnum <pnum>

use strict;
use DBI;

my $pnum;

while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    else {die "Unknown argument $arg";}
}

die "No pnum given" unless defined($pnum);

my $dbname = "agora";
my $username = "agora";
my $dbh;
my $sth;
my $row;

$dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "")
    or die "Unable to connect to database";

$sth = $dbh->prepare("SELECT body FROM proposal_pool where cpid = ? or dnum::text = ?")
    or die "Unable to prepare sql query";

$sth->execute($pnum, $pnum) or die "Unable to execute sql query";

$row = $sth->fetchrow_arrayref or die "Failed to retrieve proposal";

print $$row[0], "\n";

$sth->finish;
$dbh->disconnect;
