# Syllabloom feature tour

[中文说明](FEATURE_TOUR.zh-CN.md)

These screenshots were captured from a locally running Syllabloom instance. They contain no account credentials, API keys, submitted coursework, or AI-generated answers. The short draft in the assignment capture is deliberately unsaved demonstration text.

## 1. Local course library

![English course library](images/01-course-library-en.jpg)

The dashboard is a local index of the courses you import. It keeps course progress, local records, and certificates on your machine; it does not require a Syllabloom account.

## 2. Bilibili playback inside the course page

![Bilibili in-page player after the login return](images/02-bilibili-login-return-en.jpg)

The Bilibili video plays in Syllabloom's own HTML5 player inside the course workspace. The quality menu lists the tiers Bilibili returns for your account, and switching keeps the playback position. **Scan to sign in** shows the official Bilibili QR code inside the page; scanning it with the mobile app signs you in without leaving Syllabloom. Session cookies stay in the local database — they are never displayed or uploaded — and watch progress counts toward course completion like YouTube lectures. Anonymous playback is usually capped around 480P; signed-in playback uses your own account's entitlements.


## 3. Write an assignment in the browser

![In-browser assignment workbench](images/03-assignment-workbench-en.jpg)

Each imported public assignment has its own workbench. The left pane preserves the public brief and linked resources; the right pane is a Markdown editor. Save a draft locally as often as you want, then create an immutable submission version. A version is not sent to an AI provider until you select it and explicitly acknowledge the request.

## 4. Versioned feedback guardrails

![Saved-version and feedback area](images/08-assignment-feedback-en.jpg)

The feedback area remains inactive until a local submission version exists and the learner checks the acknowledgement for that exact version. This prevents a draft from being sent accidentally and keeps any AI result attached to a stable local snapshot. The capture intentionally shows the pre-feedback state; no configured provider was invoked to create documentation data.

## 5. Local AI and Obsidian configuration

![Local AI settings](images/04-local-ai-settings-en.jpg)

Settings support an existing Obsidian vault, a watch-completion threshold, Codex CLI, or an OpenAI-compatible endpoint such as Ollama, LM Studio, or vLLM. Keys are stored only in the local application database and are never returned to the browser. The visible values in this capture are placeholders, not a configured key.

## 6. English-first interface, Chinese and dark theme

![Chinese dark course workspace](images/05-chinese-dark-course.jpg)

The first-run interface is English. Use the footer links to switch to Chinese and the theme button to choose Light or Dark; both preferences are retained in the browser. Imported course titles and external-source text remain as supplied.

## 7. Attach a learner-selected Bilibili source

![Bilibili source selector](images/06-bilibili-source-en.jpg)

Under any lecture, paste a direct Bilibili URL containing a `BV...` identifier. The source is explicitly marked as learner-selected and third-party, with playback rights and availability remaining controlled by Bilibili and the uploader. It is never relabeled as official course material.

## 8. Import public courses

![Public course import dialog](images/07-public-course-import-en.jpg)

Add a course from a pasted Bilibili link by default — multi-part videos split into one lecture per part — or import a public YouTube video or playlist through the official YouTube Data API, use a manual public-video fallback, or import a bounded public Stanford course URL. Login-gated resources are recorded as protected sources rather than fetched through an access-control boundary.

## A safe study workflow

1. Import a public course and verify its source links.
2. Watch an embeddable lecture in the page. For Bilibili, scan the in-page QR code to sign in, then pick a quality from the menu.
3. Open an assignment, write locally, and save a draft or immutable version.
4. Configure Codex CLI or a compatible AI provider only if you want feedback.
5. Select a saved version and explicitly confirm before requesting feedback. Results remain attached to that local snapshot.

See the [user guide](USER_GUIDE.md) for the complete operational and privacy details.
