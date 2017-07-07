<?php header("Content-type: text/html; charset=utf-8"); ?>

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
 "http://www.w3.org/TR/html4/loose.dtd">
<html>
<?php

$id = $_GET["id"];

if (preg_match('/^(\d+)-(\d+)$/', $id, $matches) == 1) {
  $sql = "pid = '${matches[2]}' and to_char(sdate, 'YY') = '${matches[1]}'";
} else if (preg_match('/^\d+$/', $id) == 1) {
  $sql = "dnum = $id";
} else {
?>
<body>Proposal not found</body></html>
<?php
  exit;
}

$database = pg_connect("dbname=agora user=apache");

if (!$database) {
  echo "<body>" . pg_last_error($database) . "</body></html>";
  exit; }

pg_query("set time zone 'GMT'");

$query = pg_query("SELECT num, proposer, ai, flags, title, body, pid, idate
FROM proposal_pool WHERE $sql");

if (!$query) {
  echo "<body>" . pg_last_error($database) . "</body></html>";
  exit; }

$row = pg_fetch_array($query);

if (!$row) {
?>
<body>Proposal not found</body></html>
<?php
  exit; }

$num = $row["num"];
$name = $row["proposer"];
$ai = $row["ai"];
$flags = $row["flags"];
$title = $row["title"];
$body = $row["body"];
$pid = $row["pid"];
$idate = $row["idate"];

$name = htmlspecialchars($name);
$title = htmlspecialchars($title);
$body = htmlspecialchars($body);

echo "<head><title>Proposal $num</title></head><body>\n";

$query = pg_query("SELECT str FROM proposal_flags
                   WHERE $flags & fid = fid ORDER BY fid");

if (!$query) {
  echo pg_last_error($database);
  exit; }

echo "<h2>Proposal $num by $name, AI=$ai";

while ($row = pg_fetch_row($query))
  echo ", $row[0]";

echo "<br>\n";
echo "$title</h2>\n\n";

echo "<hr><pre>\n";
echo $body;
echo "\n</pre><hr>\n";
echo "<h4>Proposal history:</h4>\n";

$query = pg_query($database, "SELECT action, agora_date(adate)
FROM proposal_history
WHERE pid = $pid AND pdate = '$idate' ORDER BY adate, hid");

if (!$query) {
  echo pg_last_error($database);
  exit; }

while ($row = pg_fetch_row($query)) {
  echo "<p><b>$row[1]:</b>  $row[0]</p>\n";
}
?>

<hr />
<div align=right>
  <a href="http://validator.w3.org/check?uri=referer"><img border="0"
      src="http://www.w3.org/Icons/valid-html401"
      alt="Valid HTML 4.01!" height="31" width="88"></a>
</div>

</body></html>
