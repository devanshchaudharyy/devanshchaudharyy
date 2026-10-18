# Profile activity updates

The profile cards are generated directly from GitHub's GraphQL API by
`scripts/update_profile.py`. The snake and both cards are refreshed together
by `.github/workflows/profile-snake.yml`, scheduled at minute 17 of every hour.
GitHub schedules are best effort and may start late. To refresh on demand, open
the **Refresh profile activity** workflow in Actions and select **Run workflow**.
Edits to the README, generator script or workflow also trigger a refresh.

The cards show their actual generation time in UTC. Commits, pull requests and
profile contributions cover the previous 365 days. Stars and language byte
counts use all public, owned, non-fork repositories. Repository pagination is
followed; incomplete or failed API responses fail the run and retain the last
successful assets instead of publishing zeroes. Private repository names and
code are never requested by the card generator.

Public commit totals do not include commits hidden in private repositories.
To show anonymized private activity on your profile calendar, enable
**Contribution settings > Private contributions** on your GitHub profile.
This is an account visibility preference; the workflow does not change it or
request a personal access token. GitHub can take up to 24 hours to recognize
qualifying contributions. Commits must use an email linked to the account and
be on a qualifying branch. The snake follows the contribution calendar
available to its repository-scoped token.

The generator has read-only permissions. A separate publishing job has
repository contents-write permission and stages only the four named SVG paths;
it executes no third-party snake generator. Generated images are served from this repository. GitHub and the
browser may briefly cache an image after a successful refresh.

References:

- https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions
- https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/manage-visibility-settings-for-private-contributions-and-achievements
- https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
