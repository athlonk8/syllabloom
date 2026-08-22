# User guide

[中文](USER_GUIDE.zh-CN.md)

Syllabloom is designed for study that remains understandable months later: source links remain attached, work is separated from originals, and your answer lives in a normal Markdown file you control.

## A recommended study loop

1. Import a public course.
2. Watch an embeddable lecture in Syllabloom.
3. Export notes to Obsidian when you are ready to write.
4. For a public official assignment, download the source and create the workspace.
5. Write or revise Answer.md yourself.
6. Submit only when you want feedback, confirm the data boundary, and review the saved feedback.
7. Repeat. Earlier submission snapshots remain available for comparison.

## Import a YouTube course

Open Add course and choose YouTube API for a public video or playlist URL. Add a YouTube Data API key in Settings first if you want automatic metadata. The importer reads the official API's title, channel, ordered videos, duration, thumbnail, description, and publication data. It does not scrape the YouTube web page.

If a key is unavailable, choose Manual fallback, enter a course name and a public video URL, and begin with that video. Manual fallback is deliberately limited: it does not claim to reconstruct a playlist from web-page scraping.

The player uses YouTube's IFrame Player API. While playing, it periodically records short watch intervals. A large jump forward is treated as a seek and is not counted as covered material. Repeated or overlapping intervals are merged, so replaying a segment does not inflate progress. The most recent saved position is used when a lecture is opened later.

Some videos cannot be embedded because the publisher disables embeds or removes the video. Syllabloom preserves the official source link and shows that the embed is unavailable; it does not redirect you automatically.

## Use a Bilibili source and your own account

Expand **Use a Bilibili source** below a lecture and paste a direct `BV...` video URL. This creates a learner-selected, third-party source; it does not turn that video into official course material.

The embedded Bilibili player requests Bilibili's high-quality mode, but the actual quality menu is controlled by Bilibili, the selected video, your account entitlement, network conditions, and browser privacy settings. Use **Sign in and return to player** to open Bilibili's own first-party login page in the current tab. Syllabloom never receives a password, QR code, or cookie. The login return target preserves the current course and lecture; after Bilibili signs you in, it returns to that page, removes the one-time handoff parameters from the URL, and reloads the iframe automatically. Use **I have signed in — reload player** only as a manual fallback. Use **Open HD on Bilibili** when your browser blocks third-party cookies or you want Bilibili's full first-party player. The in-page **Full screen** button expands the player without leaving the course workspace when the browser permits the Fullscreen API.

## Import a Stanford course

Choose Stanford URL and paste a public Stanford course page. The importer:

1. Checks the host's robots policy.
2. Fetches the supplied page and a small bounded set of selected same-host course, schedule, lecture, material, and assignment links.
3. Records discovered slides, PDFs, notebooks, GitHub links, readings, assignments, and protected resources with source-page provenance.
4. Stops at Canvas, SSO, Gradescope, and other authentication boundaries.

A page that appears login-gated is retained as a protected source. It is visible in the provenance area as requiring Stanford authentication, but is not fetched through the login screen or omitted from the record.

The import bounds are configurable with SYLLABLOOM_CRAWL_MAX_PAGES and SYLLABLOOM_CRAWL_MAX_DEPTH. Keeping them small makes imports predictable and respectful of source websites.

## Understand sources and assignments

Syllabloom does not guess whether a resource is official. A resource is treated as an official assignment only when a public official course page directly links to it. The course page, resource URL, access state, local path, checksum when downloaded, and other provenance fields remain associated with the record.

The course view separates three things:

- Official source material: a link or downloaded original from the public source.
- Personal workspace: a local place to write and test your own answer.
- Submission snapshot: an immutable copy made at the time you request feedback.

This separation means an edit to Answer.md after a submission does not alter an earlier snapshot or its feedback.

## Use Obsidian safely

Set an existing vault path in Settings, then use Export Obsidian notes or Create notes on an assignment. Syllabloom creates only its AI-Learning subtree. A typical assignment includes:

    AI-Learning/
      course-name/
        Assignments/
          assignment-key/
            Assignment.md
            Answer.md
            Feedback.md

Answer.md is shared between Syllabloom and Obsidian. Edit it in either place. If Answer.md already exists, Syllabloom preserves it rather than overwriting it.

For Docker installations, the vault must first be mounted into the container. See the [installation guide](INSTALLATION.md#docker-and-obsidian).

## Download and prepare official work

For an unprotected official assignment:

1. Select Download original. The app records files below its local LearningVault and keeps originals separate from your workspace.
2. Select Create notes. This creates the Obsidian files when a vault is configured and prepares the local workspace.
3. Select Open workspace if you want your operating system to open the validated local directory.

Protected assignments are intentionally not downloadable. Their course provenance remains visible so you know why no action is available.

## Write, save, and get feedback

Open an assignment card to use the in-browser workbench. Its left panel preserves the public assignment brief and resource links; the right panel is a Markdown answer editor. The editor writes either to the configured Obsidian `Answer.md` or to Syllabloom's local `LearningVault` when Obsidian is not configured.

Use **Save draft** as often as you want. Then use **Save submission version** to make an immutable local snapshot. Saving a snapshot does not send it to Codex, OpenAI, Stanford, or a course platform. Select an exact saved version from the local history, tick the acknowledgement, then choose **Grade with configured Codex**. The result panel shows its AI-estimated score, confidence, capability dimensions, detailed explanation, requirement-by-requirement feedback when available, strengths, issues, and topics to revisit.

Select a provider in Settings before requesting feedback.

| Provider | Workflow |
| --- | --- |
| Codex CLI | Native launch stages a copy of the assignment and runs Codex in a read-only sandbox. |
| OpenAI-compatible | The app sends a bounded request containing the staged Answer.md, public assignment context, policy text, and official-test summary when present. |
| Disabled | No AI review is requested. |

The acknowledgement checkbox is required for every grading request. This is not a one-time global consent. It confirms that you intend to send the selected staged snapshot to the configured provider. The feedback result remains attached to that snapshot, even after you revise the current answer.

When public tests are available, they run before optional AI feedback. Feedback is intended to be progressive and review-oriented rather than a complete solution. If you use a remote provider, it may have costs and its own privacy policy.

Use the saved-version list to revisit snapshots and grades. Revise your Answer.md and create another version when ready; the prior versions stay intact.

## Certificates

Syllabloom can create a local independent-learning certificate after the course meets its completion policy. Completion normally requires the configured unique video coverage threshold and passing any required public official assignments. Mastery rules, when configured, can also require assignment and average-score thresholds.

The certificate is not university-issued, accredited, sponsored, or endorsed. It does not display a university logo or claim official course credit.

## Language and accessibility

English is the first-run language. Use English or 中文 in the sidebar footer at any time. Course titles, source descriptions, and material provided by external sites are retained as supplied; changing the UI language does not translate third-party course content.

The interface follows your system color preference on first use. Use the Theme control in the sidebar footer to choose Light or Dark; the browser remembers an explicit selection.

The language controls are real links with a lang query parameter, so a saved or shared URL can request a language directly.

## Keep a healthy local record

- Back up the native data directory or Docker volume periodically.
- Keep your Obsidian vault backed up independently; it is your working knowledge base.
- Keep API keys out of screenshots, issues, commits, and shared .env files.
- Verify imported sources before treating them as course requirements.
- Revisit history instead of overwriting past work when you want to compare learning progress.

See [Installation](INSTALLATION.md) for configuration and recovery, and [Architecture](ARCHITECTURE.md) for the trust and provenance model.

For annotated, credential-free interface screenshots, see the [feature tour](FEATURE_TOUR.md).
