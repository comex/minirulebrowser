<?php header("Content-type: text/html; charset=utf-8");

function encode_status($status) {
  if ($status < 0) {
    $status = -$status;
    return "status_n$status";
  } else {
    return "status_$status";
  }
}

$database = pg_connect("dbname=agora user=apache");
if (!$database) {
  echo pg_last_error($database);
  exit; }

if (!pg_query("set time zone 'GMT'")) {
  echo pg_last_error($database);
  exit;
}

$query = pg_query($database, "select str, fid, short from proposal_flags order by fid");
if (!$query) {
  echo pg_last_error($database);
  exit;
}

$flaglist = pg_fetch_all($query);

$query = pg_query($database, "select str, sid from proposal_status order by sid");
if (!$query) {
  echo pg_last_error($database);
  exit;
}

$statuslist = pg_fetch_all($query);
?>

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
 "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<title>Proposal Pool</title>

<script language="JavaScript" type="text/javascript"><!--
function reset_defaults()
{
  document.query_form.pattern.value = "";
  document.query_form.field.value = "body";
  document.query_form.pattype.value = "advanced";
  document.query_form.patcs.checked = false;
<?php
foreach ($statuslist as $row) {
  if ($row['sid'] == -1 || $row['sid'] == 0 || $row['sid'] == 1) {
    echo "  document.query_form." . encode_status($row['sid']) . ".checked = true;\n";
  } else {
    echo "  document.query_form." . encode_status($row['sid']) . ".checked = false;\n";
  }
}
foreach ($flaglist as $row) {
  echo "  document.query_form.flag_${row['fid']}.checked = false;\n";
} ?>
  document.query_form.sortby.value = "status";
  document.query_form.sortdir.value = "ASC";
}
//--></script>

</head>
<body>

<?php

$formdata = $_REQUEST;
$globals = array('sortby', 'sortdir', 'pattern', 'field', 'pattype', 'patcs');

foreach ($globals as $varname) {
  if (!isset($formdata[$varname])) {
    $formdata[$varname] = '';
  }
  $$varname =& $formdata[$varname];
}

if ($sortby != "cpid" and $sortby != "dnum" and $sortby != "title" and
    $sortby != "proposer" and $sortby != "ai" and $sortby != "sdate" and
    $sortby != "chamber" and $sortby != "status" and $sortby != "ddate") {
  $sortby = "status";
}

if ($sortdir != "ASC" and $sortdir != "DESC") {
  $sortdir = "ASC";
}

if ($pattype != "advanced" and $pattype != "extended" and
    $pattype != "basic" and $pattype != "exact" and
    $pattype != "tokens") {
  $pattype = "advanced";
}

if ($patcs == "on") {
  $patcs = TRUE;
} else {
  $patcs = FALSE;
}

if (!get_magic_quotes_gpc()) {
  $pattern = addslashes($pattern);
}

if ($field != "cpid" and $field != "dnum" and $field != "title" and
    $field != "proposer" and $field != "ai" and $field != "sdate" and
    $field != "ddate" and $field != "body") {
  $field = "body";
}

$flag_filter = 0;
foreach ($flaglist as $row) {
  if (isset($formdata["flag_${row['fid']}"])) {
    $flag_filter |= $row['fid'];
  }
}

if (sizeof($_GET) == 0 && sizeof($_POST) == 0) {
  $status_filter = array(-1, 0, 1);
} else {
  $status_filter = array();
  foreach ($statuslist as $row) {
    if (isset($formdata[encode_status($row['sid'])])) {
      array_push($status_filter, $row['sid']);
    }
  }
}

echo "<form name=\"query_form\" action=\"#\" method=\"post\">\n";
echo "<center>\n";
echo "<table border=1 cellspacing=0>\n";
echo "<tr><td colspan=2>\n";
echo "<table border=0 cellspacing=0>\n";
echo "<tr>\n";
echo "<td>Search Pattern:</td>\n";
echo "<td>Search In:</td>\n";
echo "<td>Search Type:</td>\n";
echo "<td>Match Case:</td>\n";
echo "</tr>\n";
echo "<tr>\n";
echo "<td><input type=\"text\" size=50 name=\"pattern\" value=\"" .
  htmlspecialchars(stripslashes($pattern)) . "\"></td>\n";
echo "<td>\n";
echo "<select name=\"field\">\n";
foreach (array('body'=>'Body', 'cpid'=>'P#', 'dnum'=>'D#', 'title'=>'Title',
               'proposer'=>'Proposer', 'ai'=>'AI', 'sdate'=>'Date',
               'ddate'=>'Distributed') as $key => $val) {
  echo "<option ";
  if ($field == $key) {
    echo "selected ";
  }
  echo "value=\"$key\">$val</option>\n";
}
echo "</select>\n";
echo "</td>\n";
echo "<td>\n";
echo "<select name=\"pattype\">\n";
foreach (array('exact'=>'Exact', 'tokens'=>'Match Tokens',
               'basic'=>'Basic Regex', 'extended'=>'Extended Regex',
               'advanced'=>'Advanced Regex') as $key => $val) {
  echo "<option ";
  if ($pattype == $key) {
    echo "selected ";
  }
  echo "value=\"$key\">$val</option>\n";
}
echo "</select>\n";
echo "</td>\n";
echo "<td>\n";
echo "<input type=\"checkbox\" name=\"patcs\"";
if ($patcs) {
  echo " checked";
}
echo " />\n";
echo "</td>\n";
echo "</tr>\n";
echo "</table>\n";
echo "</td></tr>\n";
echo "<tr><td valign=top>\n";
echo "<table border=0 cellspacing=0>\n";
echo "<tr><td colspan=2>Limit by Status:</td></tr>\n";
$i = 0;
echo "<tr>\n";
foreach ($statuslist as $row) {
  if ($i == 2) {
    echo "</tr><tr>\n";
    $i = 1;
  } else {
    ++$i;
  }
  echo "<td align=left>\n";
  echo "<input type=checkbox name=\"" . encode_status($row['sid']) . "\"";
  if (in_array($row['sid'], $status_filter)) {
    echo " checked";
  }
  echo " /> ${row['str']}";
  echo "</td>\n";
}
echo "</tr>\n";
echo "</table>\n";
echo "</td><td valign=top>\n";
echo "<table border=0 cellspacing=0>\n";
echo "<tr><td colspan=2>Limit by Flags:</td></tr>\n";
$i = 0;
echo "<tr>\n";
foreach ($flaglist as $row) {
  if ($i == 2) {
    echo "</tr><tr>\n";
    $i = 1;
  } else {
    ++$i;
  }
  echo "<td align=left>\n";
  echo "<input type=checkbox name=\"flag_${row['fid']}\"";
  if ($flag_filter & intval($row['fid'])) {
    echo " checked";
  }
  echo " /> ${row['str']}";
  echo "</td>\n";
}
echo "</tr>\n";
echo "</table>\n";
echo "</td></tr>\n";
echo "<tr><td align=center>\n";
echo "Sort By: <select name=\"sortby\">\n";
foreach (array('cpid'=>'P#', 'dnum'=>'D#', 'title'=>'Title',
               'proposer'=>'Proposer', 'ai'=>'AI', 'sdate'=>'Date',
               'chamber'=>'Chamber', 'status'=>'Status',
               'ddate'=>'Distributed') as $key => $val) {
  echo "<option ";
  if ($sortby == $key) {
    echo "selected ";
  }
  echo "value=\"$key\">$val</option>\n";
}
echo "</select>\n";
echo "Order: <select name=\"sortdir\">\n";
foreach (array('ASC'=>'Ascending', 'DESC'=>'Descending') as $key => $val) {
  echo "<option ";
  if ($sortdir == $key) {
    echo "selected ";
  }
  echo "value=\"$key\">$val</option>\n";
}
echo "</select>\n";
echo "</td><td align=center>\n";
echo "<input type=submit value=\"Search\" />\n";
echo "<input type=reset value=\"Reset\" />\n";
echo "<input type=button value=\"Reset to Default\" onclick=\"reset_defaults()\" />\n";
echo "</td></tr>\n";
echo "</table>\n";
echo "</center>\n";
echo "</form>\n";

$sql = <<<EndSQL
SELECT cpid, CASE WHEN statusid=2 THEN dnum ELSE null END,
         title, proposer, ai, agora_date(sdate), chamber,
         status, agora_date(ddate), flags
FROM proposal_pool
WHERE true
EndSQL;

if (strlen($pattern) > 0) {
  if ($field == "sdate" || $field == "ddate") {
    $field = "agora_date($field)";
  }

  $fields = array($field);

  $sql .= " AND (false";
  foreach ($fields as $field_one) {
    if ($patcs) {
      if ($pattype == 'exact') {
        $sql .= " OR strpos($field_one::text, '$pattern') > 0";
      } else if ($pattype == 'tokens') {
        $tokens = explode(' ', $pattern);
        $sql .= " OR (true";
        foreach ($tokens as $token) {
          $sql .= " AND strpos($field_one::text, '$token') > 0";
        }
        $sql .= ")";
      } else {
        $sql .= " OR $field_one::text ~ '$pattern'";
      }
    } else {
      if ($pattype == 'exact') {
        $sql .= " OR strpos(upper($field_one::text), upper('$pattern')) > 0";
      } else if ($pattype == 'tokens') {
        $tokens = explode(' ', $pattern);
        $sql .= " OR (true";
        foreach ($tokens as $token) {
          $sql .= " AND strpos(upper($field_one::text), upper('$token')) > 0";
        }
        $sql .= ")";
      } else {
        $sql .= " OR $field_one::text ~* '$pattern'";
      }
    }
  }
  $sql .= ")";
}

if (sizeof($status_filter) > 0) {
  $sql .= " AND (false";
  foreach ($status_filter as $sid) {
    $sql .= " OR statusid = $sid";
  }
  $sql .= ")";
}

if ($flag_filter > 0) {
  $sql .= " AND flags & $flag_filter = $flag_filter";
}

$sql .= " ORDER BY $sortby $sortdir, cpid ASC";

// echo $sql;

if ($pattype != 'exact' && $pattype != 'tokens') {
  if (!pg_query($database, "SET regex_flavor TO '$pattype'")) {
    echo pg_last_error($database);
    exit;
  }
}

$query = pg_query($database, $sql);

if (!$query) {
  echo pg_last_error($database);
  exit; }

echo "\n<table border=1><tr>\n";
echo "<th>P#</th>\n";
echo "<th>D#</th>\n";
echo "<th>Title</th>\n";
echo "<th>Proposer</th>\n";
echo "<th>AI</th>\n";
echo "<th>Date (GMT)</th>\n";
echo "<th>Chamber</th>\n";
echo "<th>Status</th>\n";
echo "<th>Distributed</th>\n";
echo "<th>Flags</th></tr>\n";


while ($row = pg_fetch_array($query)) {

  $pnum = $row["cpid"];
  $flags = $row["flags"];

  echo "<tr><td><a href=\"view_proposal.php?id=$pnum\">$pnum</a></td>\n";

  for ($j = 1; $j <= 8; $j++)
    echo "<td>$row[$j]</td>\n";

  echo "<td>";
  foreach ($flaglist as $row2) {
    if (intval($flags) & intval($row2['fid'])) {
      echo $row2['short'];
    }
  }
  echo "</td></tr>\n";
}
?>

</table>

<p>O: Ordinary D: Democratic P: Parliamentary
<br>d: disinterested  u: urgent  s: sane  c: contested  t: takeover
<br>+: positive advertising  -: negative advertising
</p>
<hr />
<div align=right>
  <a href="http://validator.w3.org/check?uri=referer"><img border="0"
      src="http://www.w3.org/Icons/valid-html401"
      alt="Valid HTML 4.01!" height="31" width="88"></a>
</div>

</body>
</html>
