#!/usr/bin/perl

# Syntax: set_flags.pl -pnum <pnum> -flags <flags>
#                      [-date <date> -comment <comment>]
#
# Flag format example: -flags aB,~cd,E
#   Would set flags a, B, E and clear flags c, d
#
# Available comment substitutions: $#, $T, $I

use strict;
use DBI;

my ($pnum, $comment, $date);
my @flaglist;

while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-p/ && !index('-pnum', $arg)) {$pnum = shift @ARGV;}
    elsif ($arg =~ m/^-f/ && !index('-flags', $arg)) {push (@flaglist, split (/,/, shift (@ARGV)));}
    elsif ($arg =~ m/^-c/ && !index('-comment', $arg)) {$comment = shift @ARGV;}
    elsif ($arg =~ m/^-d/ && !index('-date', $arg)) {$date = shift @ARGV;}
    else {die "Unrecognized option: $arg";}
}

die "No pnum given" unless defined($pnum);
die "No flags given" unless @flaglist > 0;
die "No date given" if defined($comment) && !defined($date);

my @flags;

foreach my $flags (@flaglist) {
    if ($flags =~ m/^(\~?)([a-zA-Z]+)$/) {
        my $clr = $1;
        my $flags = $2;
        push (@flags, map($clr . $_, split (//, $flags)));
    } else {
        die "Invalid flag format: $flags";
    }
}

my $sql = "SELECT fid, short FROM proposal_flags WHERE false";

foreach my $flag (@flags) {
    if ($flag =~ m/([a-zA-Z])$/) {
        $sql .= " OR short = '$1'";
    } else {
        die "Error: invalid flag $flag";
    }
}



my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my ($sth, $row, $rv);


$sth = $dbh->prepare($sql)
    or die "Unable to prepare SQL query";

$sth->execute or die "Unable to execute SQL query";

my %flagval;
while (my $row = $sth->fetchrow_arrayref) {
    $flagval{$$row[1]} = $$row[0];
}

die "Invalid or repeated flags" unless scalar(keys(%flagval))==scalar(@flags);


my $set = 0;
my $clr = 0;

foreach my $flag (@flags) {
    if ($flag =~ m/^~([a-zA-Z])$/) {
        $clr |= $flagval{$1};
    } elsif ($flag =~ m/^([a-zA-Z])$/) {
        $set |= $flagval{$1};
    } else {
        die "Invalid flag $flag";
    }
}

$sth = $dbh->prepare("SELECT pid, idate, title, cpid FROM proposal_pool WHERE num = ?")
    or die "Unable to prepare SQL query";

$sth->execute($pnum) or die "Unable to execute SQL query";

my $row = $sth->fetchrow_arrayref;
if (!defined($row)) {
    die "Unable to fetch proposal information"; }

my $pid = $$row[0];
my $idate = $$row[1];
my $title = $$row[2];
my $cpid = $$row[3];
$sth->finish;


$sth = $dbh->prepare("UPDATE proposal SET flags = (flags | ?) & ~(?::integer) " .
                     "WHERE pid = ? AND idate = ?")
    or die "Failed to prepare SQL query";
$sth->execute($set, $clr, $pid, $idate) or die "Failed to update proposal";


if (defined($comment)) {
    $sth = $dbh->prepare("INSERT INTO proposal_history (action, adate, pid, pdate) " .
                         "VALUES (?, ?, ?, ?)")
        or die "Failed to prepare SQL query";

    $comment =~ s/\$\#/$cpid/g;
    $comment =~ s/\$T/$title/g;
    $comment =~ s/\$I/"$title" ($cpid)/g;

    $sth->execute($comment, $date, $pid, $idate)
        or die "Failed to insert history comment";
}


$dbh->commit or die "Unable to commit";
$dbh->disconnect;
