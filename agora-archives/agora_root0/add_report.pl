#!/usr/bin/perl

# Syntax: add_report.pl <type> <date>
# Pass body via stdin

use strict;
use DBI;

if( scalar @ARGV < 2 ) {
    die "Not enough args"; }

my $report_type = @ARGV[0];
my $report_published = @ARGV[1];
my $report_body = "";

while (<STDIN>) {
    $report_body .= $_; }

if (length $report_body == 0) {
    die "No report body";
}

my $dbname = "agora";
my $username = "agora";
my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "")
    or die "Unable to connect to database";

my $sth = $dbh->prepare("INSERT INTO report (type, published, body) " .
                       "VALUES (?, ?, ?)")
    or die "Unable to prepare SQL query";

my $rv = $sth->execute ($report_type, $report_published, $report_body);

if (!defined $rv || $rv < 1) {
    die "Failed to insert report"; }

$dbh->disconnect;
