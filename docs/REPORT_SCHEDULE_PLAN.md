# EGX report schedule

The intended Cairo-local report time is 09:00 and opening-hour quote review is 11:00, Sunday through Thursday, excluding configured holidays. GitHub Actions cron uses UTC, so both Cairo UTC+2 and UTC+3 slots must be scheduled and gated by local wall clock. Quotes are snapshots and do not equal a fresh full analysis.
