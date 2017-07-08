#!/usr/bin/perl

# Syntax: reset_pid_seq.pl [<next_pid>]

use strict;
use DBI;

my $last_pid = shift @ARGV || 1;

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my $sth = $dbh->prepare("SELECT setval('proposal_pid_seq', ?, 'f')")
    or die "Unable to prepare SQL query";

$sth->execute($last_pid) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row) || $$row[0] != $last_pid) {
    die "Failed to reset sequence";
}
$sth->finish;

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
