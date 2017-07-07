#!/usr/bin/perl

# Syntax: cp_proposal.pl -dnum <dnum> -date <date> -comment <comment>
#                        [-complacent] [-sanitized] [-veto] [-newpid <pid>]
#                        [-newdnum <dnum>]
#
# Comment variables:
# $# -> new proposal number       $@ -> old distribution number
# $T -> proposal title
# $I -> equivalent to "$T" ($@)   $J -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($dnum, $date, $comp_flag, $san_flag, $veto_flag, $comment, $newpid, $newdnum);

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-dn/ && !index('-dnum', $arg)) {$dnum = shift @ARGV;}
    elsif ($arg =~ m/^-da/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
#    elsif ($arg =~ m/^-comp/ && !index('-complacent', $arg)) {$comp_flag = 1;}
#    elsif ($arg =~ m/^-s/ && !index('-sanitized', $arg)) {$san_flag = 1;}
    elsif ($arg =~ m/^-v/ && !index('-veto', $arg)) {$veto_flag = 1;}
    elsif ($arg =~ m/^-newp/ && !index('-newpid', $arg)) {$newpid = shift @ARGV;}
    elsif ($arg =~ m/^-newd/ && !index('-newdnum', $arg)) {$newdnum = shift @ARGV;}
    else {die "Unrecognized option: $arg";}
}

die "No dnum given" unless defined($dnum);
die "No date given" unless defined($date);
die "No comment given" unless defined($comment);
die "-complacent, -sanitized, and -veto are mutually exclusive" if $comp_flag + $san_flag + $veto_flag > 1;

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

# Use dnum to retrieve original proposal information
my $sth = $dbh->prepare("SELECT pid, title, body, proposer_id, " .
                        "sdate, ai, flags, idate " .
                        "FROM proposal WHERE dnum = ?")
    or die "Unable to prepare SQL query";

$sth->execute($dnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my ($oldpid, $title, $body, $proposer_id, $sdate, $ai, $flags, $idate) = @$row;
$sth->finish;

# If new pid not specified, grab the next one.
if (!defined($newpid)) {
    $sth = $dbh->prepare("SELECT to_char(nextval('\"proposal_pid_seq\"'::text), 'FM099')")
        or die "Unable to prepare SQL query";

    $sth->execute or die "Unable to execute SQL query";

    $row = $sth->fetchrow_arrayref;
    if (!defined $row) {
        die "Unable to fetch next available pid"; }

    $newpid = $$row[0];
    $sth->finish;
}

# Set new attributes for complacent / sanitized / vetoed proposals
my $status;
if ($comp_flag) {
    $status = 1;  # distributable
    $flags = ($flags & ~(1 | 4)) | 2;  # democratic
} elsif ($san_flag) {
    $status = 1;  # distributable
    $flags = ($flags & ~(1 | 4)) | 2 | 32;  # democratic, sane
} elsif ($veto_flag) {
    $status = 1;  # distributable
    $flags = ($flags & ~(1 | 4)) | 2;  # democratic
    $ai += 1;
} else {
    $status = 0;  # undistributable
}

# insert new proposal
$sth = $dbh->prepare("INSERT INTO proposal (pid, title, body, proposer_id, " .
                     "sdate, status, ai, flags, idate, dnum) ".
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    or die "Unable to prepare SQL query";

my $rv = $sth->execute($newpid, $title, $body, $proposer_id, $sdate, $status,
                       $ai, $flags, $date, $newdnum);

if (!defined $rv || $rv < 1) {
    die "Failed to insert proposal"; }

# retrieve canonical pid of new proposal
$sth = $dbh->prepare("SELECT num FROM proposal_pool WHERE pid = ? " .
                     "AND idate = ?")
    or die "Unable to prepare SQL query";
$sth->execute($newpid, $date) or die "Unable to execute SQL query";
my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch canonical pid of new proposal";
}
my $cpid = $$row[0];
$sth->finish;


# Perform variable substitution on comment string
$comment =~ s/\$\#/$cpid/g;
$comment =~ s/\$\@/$dnum/g;
$comment =~ s/\$T/$title/g;
$comment =~ s/\$I/\"$title\" \($dnum\)/g;
$comment =~ s/\$J/\"$title\" \($cpid\)/g;

# Add comment
$sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, " .
                     "pid, pdate, in_reports) VALUES (?, ?, ?, ?, ?)")
    or die "Unable to prepare SQL query";

$rv = $sth->execute($comment, $date, $oldpid, $idate, 't');
if (!defined $rv || $rv < 1) {
    die "Failed to insert proposal history comment"; }

$rv = $sth->execute($comment, $date, $newpid, $date, 'f');
if (!defined $rv || $rv < 1) {
    die "Failed to insert proposal history comment"; }

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
