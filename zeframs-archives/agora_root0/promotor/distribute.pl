#!/usr/bin/perl

# Syntax: distribute.pl -date <date> [-dnum <dnum_or_range> [-dnum ...]]
#                       [-force_stalled]
#
# Marks distributable proposals with assigned dnums as distributed
# The -force_stalled option is used to to distribute stalled proposals as well

use strict;
use DBI;

my $date;
my $force = 'f';

my $num_proposals;
my @proposals;
my @dnums;

# Read in arguments
while (defined(my $arg = shift @ARGV)) {
    $arg = lc $arg;
    if ($arg =~ m/^-da/ && !index('-date', $arg)) {$date = shift @ARGV;}
    elsif ($arg =~ m/^-f/ && !index('-force_stalled', $arg)) {$force = 't';}
    elsif ($arg =~ m/^-dn/ && !index('-dnum', $arg)) {
        my $dnums = shift @ARGV;
        if ($dnums =~ m/(\d+)-(\d+)/) {
            for (my $i = $1; $i <= $2; ++$i) {
                push @dnums, $i;
            }
        } elsif ($dnums =~ m/(\d+)/) {
            push @dnums, $1;
        } else {
            die "No dnums found: $dnums";
        }
    } else {die "Unrecognized option: $arg";}
}

die "Date not given" unless defined($date);


my $dbname = "agora";
my $username = "agora";

my $dbh = DBI->connect("dbi:Pg:dbname=$dbname", $username, "",
                       { AutoCommit => 0 })
    or die "Unable to connect to database";

my ($sth, $sth2, $sth3);

# Build SQL query to fetch distributable proposals with dnums
if (@dnums > 0) {  # dnums specified at command line
    my $sql = "SELECT to_char(idate, 'YY-'::text) || to_char(pid, 'FM099'::text) AS cpid, " .
        "pid, idate, dnum, title FROM proposal " .
        "WHERE (status = 1 AND (NOT is_stalled(flags, ai) OR ?)) AND (false ";
    foreach my $dnum (@dnums) {
        $sql .= "OR dnum = '$dnum' ";
    }
    $sql .= ") ORDER BY dnum";
    $sth = $dbh->prepare($sql) or die "Unable to prepare SQL query";
} else {  # no dnums specified, use all eligible proposals
    $sth = $dbh->prepare("SELECT to_char(idate, 'YY-'::text) || to_char(pid, 'FM099'::text) AS cpid, " .
                         "pid, idate, dnum, title FROM proposal " .
                         "WHERE (status = 1 AND (NOT is_stalled(flags, ai) OR ?)) " .
                         "AND dnum IS NOT NULL " .
                         "ORDER BY dnum")
        or die "Unable to prepare SQL query";
}


# Fetch distributable proposals with dnums
$sth->execute($force) or die "Unable to execute SQL query";
$num_proposals = $sth->rows;
if ($num_proposals < 1) {die "No assigned distributable proposals found";}


if ($num_proposals > 1) {
    # If more than one proposal, use separate history entries for each
    # proposal history page, and a single collective history entry for
    # reports.
    $sth2 = $dbh->prepare("INSERT INTO proposal_history " .
                          "(action, adate, pid, pdate, in_reports) " .
                          "VALUES (?, ?, ?, ?, 'f')")
        or die "Unable to prepare SQL query";
} else {
    # If only one proposal, use the same history entry for the reports
    # and the proposal history page
    $sth2 = $dbh->prepare("INSERT INTO proposal_history " .
                          "(action, adate, pid, pdate, in_reports) " .
                          "VALUES (?, ?, ?, ?, 't')")
        or die "Unable to prepare SQL query";
}

$sth3 = $dbh->prepare("UPDATE proposal SET status = 2, ddate = ? " .
                      "WHERE pid = ? AND idate = ?")
    or die "Unable to prepare SQL query";


@dnums = ();
# Loop over each proposal
while (defined(my $row = $sth->fetchrow_arrayref)) {
    my ($cpid, $pid, $idate, $dnum, $title) = @$row;

    # Add the history item for this proposal
    my $rv = $sth2->execute("\"$title\" ($cpid) is distributed as proposal $dnum.",
                            $date, $pid, $idate);

    if (!defined($rv) || $rv < 1) {
        die "Failed to insert history item for $cpid";
    }

    # Mark this proposal distributed
    $rv = $sth3->execute($date, $pid, $idate);
    if (!defined($rv) || $rv != 1) {
        die "Failed to update proposal $cpid";
    }

    # Bookkeeping for collective history item
    push @proposals, "\"$title\" ($cpid)";
    push @dnums, $dnum;
}


if ($num_proposals > 1) {
    # Add collective history item for reports
    $sth = $dbh->prepare("INSERT INTO proposal_history (action, adate) " .
                         "VALUES (?, ?)")
        or die "Failed to prepare SQL query";

    my $comment = '';
    for (my $i = 0; $i < $num_proposals; ++$i) {
        if ($i < $num_proposals - 2) {
            $comment .= $proposals[$i] . ', ';
        } elsif ($i == $num_proposals - 2) {
            $comment .= $proposals[$i] . ' and ';
        } else {
            $comment .= $proposals[$i];
        }
    }

    $comment .= ' are distributed as proposals ';

    $comment .= $dnums[0];
    my $range_start = $dnums[0];
    for (my $i = 1; $i < $num_proposals; ++$i) {
        if ($dnums[$i] != $dnums[$i-1] + 1) {
            if ($range_start != $dnums[$i-1]) {
                $comment .= '-' . $dnums[$i-1];
            }
            $comment .= ', ' . $dnums[$i];
            $range_start = $dnums[$i];
        }
    }
    if ($range_start != $dnums[-1]) {
        $comment .= '-' . $dnums[-1];
    }
    $comment .= '.';

    my $rv = $sth->execute($comment, $date);
    if (!defined $rv || $rv < 1) {
        die "Failed to insert proposal history comment";
    }
}

$dbh->commit or die "Unable to commit";
$dbh->disconnect;
