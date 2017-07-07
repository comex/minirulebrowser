#!/usr/bin/perl

# Syntax: delete_proposal.pl -pnum <pnum> [-force]
# Deletes ALL reference to the given proposal.  Use with caution.

use strict;
use DBI;

my ($pnum, $force);

$force = 0;

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-f/ && !index('-force', $arg)) {$force = 1;}
    else {die "Unrecognized argument: $arg";}
}

die "No pnum given" unless defined $pnum;

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

# Fetch proposal information from dnum or cpid
my $sth = $dbh->prepare("SELECT pid, idate, title FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
my $title = $$row[2];
$sth->finish;

# Require user to confirm action
if (!$force) {
    print "This will delete ALL reference to proposal $pnum ($title).  Are you sure?\n";
    my $response = <STDIN>;
    if ($response !~ /^[yY]/) {
        die "Aborting due to user input";
    }
}

# Delete proposal
$sth = $dbh->prepare("DELETE FROM proposal WHERE pid = ? AND idate = ?")
    or die "Unable to prepare SQL query";
my $rv = $sth->execute($pid, $idate);

if (!defined $rv || $rv < 1) {
    die "Failed to delete proposal"; }

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
