# back-announcements

The announcement listener rotates globally through variants 1, 2, 3, and 4
across playback updates. Variants 3 and 4 are the year-based announcements.
For each track, missing files are skipped in rotation order; the next update
starts after the variant actually selected. Files may be in subdirectories of
`/mnt/zara/Song Announcements`.

If no variant exists for a track, the listener selects `DUMMY~0.mp3` without
advancing the rotation. Database-error notifications retain their dummy fallback.
The selected file is exposed through the existing relative
`ANNOUNCEMENT~0.mp3` symlink.

Run the rotation tests with `python -m unittest test_set_announcement_file`.
