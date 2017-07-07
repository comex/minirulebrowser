#!/usr/bin/perl

# Syntax: add_comment.pl -date <date> -comment <comment>
#                        [-pnum <pnum> [-suppress]]
#
# Comment variables:
# $# -> proposal number          $T -> proposal title
# $I -> equivalent to "$T" ($#)

use strict;
use DBI;

my ($pnum, $date, $comment, $in_reports);

$in_reports = 't';

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-d/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
    elsif ($arg =~ m/^-s/ && !index('-suppress', $arg)) {$in_reports = 'f';}
    else {die "Unrecognized option: $arg";}
}

die "Date not specified" unless defined($date);
die "Comment not specified" unless defined($comment);

if ($in_reports eq 'f' && !defined($pnum)) {
    die "-suppress given without -pnum";
}

my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my ($pid, $idate, $title);
if (defined($pnum)) {
    # Retrieve proposal information
    my $sth = $dbh->prepare("SELECT num, pid, idate, title " .
                            "FROM proposal_pool WHERE cpid = ? OR dnum::text = ?")
        or die "Unable to prepare SQL query";

    $sth->execute($pnum, $pnum) or die "Unable to execute SQL query";

    my $row = $sth->fetchrow_arrayref;
    die "Unable to fetch proposal information" unless defined($row);

    $pnum = $$row[0];
    $pid = $$row[1];
    $idate = $$row[2];
    $title = $$row[3];
    $sth->finish;
}

# Perform variable substitution on comment string
$comment =~ s/\$\#/$pnum/g;
$comment =~ s/\$T/$title/g;
$comment =~ s/\$I/"$title" ($pnum)/g;

# Add comment
my $sth = $dbh->prepare("INSERT INTO proposal_history " .
                        "(action, adate, pid, pdate, in_reports) " .
                        "VALUES (?, ?, ?, ?, ?)")
    or die "Unable to prepare SQL query";
my $rv = $sth->execute($comment, $date, $pid, $idate, $in_reports);

if (!defined $rv || $rv < 1) {
    die "Failed to insert comment";
}


$dbh->commit or die "Unable to commit";
$dbh->disconnect;
