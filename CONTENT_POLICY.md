# Instagram Reel content policy

`reel_content_policy.py` is a fail-closed gate used by `reel_publisher.py` and both GitHub Actions workflows.

Every queued item must include `content_policy.version: 1` and pass these checks:

- The first two caption lines contain at least one declared search keyword.
- The caption has 4–5 unique hashtags. `#shorts` is forbidden and at least one tag must be topic-specific.
- Performance is reviewed at 24 and 72 hours.
- A newly produced asset uses `mode: full`, shows the visible result in the first two seconds, changes one controlled variable, shows a second visible result, and has a bilingual `pair_id`.
- Assets that existed when this rule was introduced may use `mode: baseline_asset` only when their exact item ID and video hash appear in `reel_content_policy_baseline.json`. Changing the video hash makes the exemption fail.

The Korean editorial queue alternates food science and general physics while both backlogs are available. Scheduling and queue edits must preserve published entries and any active publication intent.

`.github/workflows/reel-performance.yml` runs every three hours. For items carrying this policy, `reel_performance.py` records one sample shortly after 24 hours and another shortly after 72 hours in the account's `performance.json`. Each sample includes views, reach, average watch time, shares per 1,000 reached accounts, and saves per 1,000 reached accounts.
