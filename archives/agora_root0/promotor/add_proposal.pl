#!/usr/bin/perl
# Syntax: add_proposal -title <title> -proposer <proposer> -date <date>
#                      [-ai <ai>] [-distributable] [-flags <flags>]
#                      [-pid <pid>] [-dnum <dnum>] [-comment <comment>]
# Pass body via stdin
#
# Comment variables:
# $# -> proposal number     $T -> proposal title
# $P -> proposer's name     $I -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($title, $proposer, $date, $ai, $status, $flags, $pid, $dnum, $comment);

$ai = 1;
$status = 0;
$flags = '';
$comment = '$P submits $I.';

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-t/ && !index('-title', $arg)) { $title = shift @ARGV; }
    elsif ($arg =~ m/^-pr/ && !index('-proposer', $arg)) { $proposer = shift @ARGV; }
    elsif ($arg =~ m/^-da/ && !index('-date', $arg)) { $date = shift @ARGV; }
    elsif ($arg =~ m/^-a/ && !index('-ai', $arg)) { $ai = shift @ARGV; }
    elsif ($arg =~ m/^-di/ && !index('-distributable', $arg)) { $status = 1; }
    elsif ($arg =~ m/^-f/ && !index('-flags', $arg)) { $flags = shift @ARGV; }
    elsif ($arg =~ m/^-pi/ && !index('-pid', $arg)) { $pid = shift @ARGV; }
    elsif ($arg =~ m/^-dn/ && !index('-dnum', $arg)) { $dnum = shift @ARGV; }
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) { $comment = shift @ARGV; }
    else { die "Unrecognized option: $arg"; }
}

if (!defined($title)) { die "No title specified (use -title)"; }
if (!defined($proposer)) { die "No proposer specified (use -proposer)"; }
if (!defined($date)) { die "No date specified (use -date)"; }
#if (!defined($comment)) { die "No comment specified (use -comment)"; }

# Set default chamber
if ($flags !~ m/[ODP]/) {
#    if ($ai >= 2) {
#        $flags .= 'D';
#    } else {
        $flags .= 'O';
#    }
}

# Read in proposal body from stdin
my $body = "";
while (<STDIN>) {
    $body .= $_; }

if (length $body == 0) {
    die "Proposal body is missing.";
}

my $dbname = "agora";
my $username = "agora";
my $password = "";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, $password,
                       { AutoCommit => 0 })
    or die "Unable to connect to database";


# Fetch proposer's eid and canonical name
my $sth = $dbh->prepare("SELECT eid, name FROM entity WHERE name ILIKE ? OR short ILIKE ?")
    or die "Unable to prepare SQL query";

$sth->execute($proposer, $proposer) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined $row) {
    die "Unable to fetch eid of proposer"; }

my $proposer_id = $$row[0];
$proposer = $$row[1];
$sth->finish;


# Compute numerical flags value
$sth = $dbh->prepare("SELECT sum(fid) FROM proposal_flags WHERE strpos(?, short) > 0")
    or die "Unable to prepare SQL query";

$sth->execute($flags) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined $row) {
    die "Unable to look up flag values"; }

my $flags_val = $$row[0];
$sth->finish;

# If pid not specified, use the next one available.
if (!defined($pid)) {
    $sth = $dbh->prepare("SELECT to_char(nextval('\"proposal_pid_seq\"'::text), 'FM099')")
        or die "Unable to prepare SQL query";

    $sth->execute or die "Unable to execute SQL query";

    $row = $sth->fetchrow_arrayref;
    if (!defined $row) {
        die "Unable to fetch next available pid"; }

    $pid = $$row[0];
    $sth->finish;
}

# Add proposal
$sth = $dbh->prepare("INSERT INTO proposal (pid, title, proposer_id, " .
                        "sdate, ai, status, flags, body, idate, dnum) ".
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    or die "Unable to prepare SQL query";

my $rv = $sth->execute($pid, $title, $proposer_id, $date, $ai, $status,
                       $flags_val, $body, $date, $dnum);

if (!defined $rv || $rv < 1) {
    die "Failed to insert proposal"; }


# Add history item
if (defined($comment)) {
    # fetch canonical proposal id
    my $sth = $dbh->prepare("SELECT num FROM proposal_pool where pid = ?" .
                            " AND idate = ?")
        or die "Unable to prepare SQL query";

    $sth->execute($pid, $date) or die "Unable to execute SQL query";
    $row = $sth->fetchrow_arrayref;
    if (!defined($row)) { die "Unable to fetch canonical pid"; }
    my $cpid = $$row[0];
    $sth->finish;

    # Perform variable substitution
    $comment =~ s/\$\#/$cpid/g;
    $comment =~ s/\$T/$title/g;
    $comment =~ s/\$P/$proposer/g;
    $comment =~ s/\$I/"$title" ($cpid)/g;

    # Add the comment
    $sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, " .
                         "pid, pdate) VALUES (?, ?, ?, ?)")
        or die "Unable to prepare SQL query";

    $rv = $sth->execute($comment, $date, $pid, $date);

    if (!defined $rv || $rv < 1) {
        die "Failed to insert proposal history comment"; }
}

if (defined($dnum)) {
    # If a dnum was specified, use it to update the dnum sequence.
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
