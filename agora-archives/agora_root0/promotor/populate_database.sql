INSERT INTO proposal_flags (fid, str, short)
VALUES (1, 'Ordinary', 'O');

INSERT INTO proposal_flags (fid, str, short)
VALUES (2, 'Democratic', 'D');

INSERT INTO proposal_flags (fid, str, short)
VALUES (4, 'Parliamentary', 'P');

INSERT INTO proposal_flags (fid, str, short)
VALUES (8, 'Disinterested', 'd');

INSERT INTO proposal_flags (fid, str, short)
VALUES (16, 'Urgent', 'u');

INSERT INTO proposal_flags (fid, str, short)
VALUES (32, 'Sane', 's');

INSERT INTO proposal_flags (fid, str, short)
VALUES (64, 'Contested', 'c');

INSERT INTO proposal_flags (fid, str, short)
VALUES (128, 'Positive Advertising', '+');

INSERT INTO proposal_flags (fid, str, short)
VALUES (256, 'Negative Advertising', '-');

INSERT INTO proposal_flags (fid, str, short)
VALUES (512, 'Takeover', 't');

INSERT INTO proposal_status (sid, str)
VALUES (0, 'Undistributable');

INSERT INTO proposal_status (sid, str)
VALUES (1, 'Distributable');

INSERT INTO proposal_status (sid, str)
VALUES (2, 'Distributed');

INSERT INTO proposal_status (sid, str)
VALUES (3, 'Removed');

-- negative values are reserved for "overlay" statuses
INSERT INTO proposal_status (sid, str)
VALUES (-1, 'Stalled');
