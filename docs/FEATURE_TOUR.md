# Syllabloom feature tour

[中文说明](FEATURE_TOUR.zh-CN.md)

These screenshots were captured from a locally running Syllabloom instance. They contain no account credentials, API keys, submitted coursework, or AI-generated answers. The short draft in the assignment capture is deliberately unsaved demonstration text.

## 1. Local course library

![English course library](images/01-course-library-en.jpg)

The dashboard is a local index of the courses you import. It keeps course progress, local records, and certificates on your machine; it does not require a Syllabloom account.

## 2. Bilibili playback inside the course page

![Bilibili in-page player after the login return](images/02-bilibili-login-return-en.jpg)

The Bilibili video remains inside the course workspace. **Sign in and return to player** opens Bilibili's first-party sign-in page in the current tab. Its return target includes the current course and lecture, so after a successful Bilibili sign-in it returns to this exact course, scrolls back to the player, removes the one-time return parameters from the URL, and reloads the in-page iframe. Syllabloom never reads a Bilibili password, QR code, or cookie.

The screenshot exercises that post-login return path locally; no Bilibili account was used to produce it. Bilibili still decides the quality choices that an account and a specific video can use. Syllabloom deliberately does not offer an external Bilibili-playback button: the iframe is sandboxed without popup or top-navigation permission, so it cannot take the surrounding learning page away from the course. If Bilibili's own player shows a “watch in Bilibili” prompt for a quality it declines to serve in an embed, that provider decision remains visible but cannot navigate the outer course page.

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

Import a public YouTube video or playlist through the official YouTube Data API, use a manual public-video fallback, or import a bounded public Stanford course URL. Login-gated resources are recorded as protected sources rather than fetched through an access-control boundary.

## A safe study workflow

1. Import a public course and verify its source links.
2. Watch an embeddable lecture in the page. For Bilibili, sign in through Bilibili's own page and return to the embedded player.
3. Open an assignment, write locally, and save a draft or immutable version.
4. Configure Codex CLI or a compatible AI provider only if you want feedback.
5. Select a saved version and explicitly confirm before requesting feedback. Results remain attached to that local snapshot.

See the [user guide](USER_GUIDE.md) for the complete operational and privacy details.
