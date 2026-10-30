# Naukri Company-Site Application Implementation Plan

## Goal

Extend the Naukri bot so a job with **Apply on company site** can be opened and its application form can be completed one job at a time. The bot should reuse verified profile data, use an interchangeable AI provider for questions that need interpretation or writing, handle multi-step forms where practical, and record a clear outcome for each job.

This document is a plan only. No runtime behavior is changed by this document.

## Current State

- `modules/naukri/naukri_apply.py` detects an external-apply button and calls `_collect_external_link()`.
- `_collect_external_link()` captures the resulting URL. When the destination opens in another tab, the tab is closed immediately when `close_tabs` is enabled; no external form is inspected or submitted.
- The external branch records the URL in the existing Naukri application history as an external link and increments the external-link counter. That currently means "link collected", not "application submitted".
- Naukri's own chatbot is implemented separately in `modules/naukri/naukri_questions.py`. It resolves configured answers first, then calls provider-specific AI functions, then asks the user or applies the configured unanswerable-question policy.
- Provider selection and client creation are hard-coded in `runNaukriBot.py`. OpenAI-compatible endpoints, Gemini, and DeepSeek are supported today; there is no shared provider contract or Anthropic adapter.
- Personal answers live across `config/personals.py`, `config/questions.py`, and `user_information_all`. Existing CSV history is job-centric and does not model an external application state machine.

## Proposed User Flow

1. Naukri detects a company-site application and opens the destination in a managed tab/window instead of closing it.
2. The bot validates the destination and checks whether it is a supported application flow.
3. It inspects the visible form, including labels, input types, required state, options, and field grouping. It does not submit anything during this inspection step.
4. It maps fields to verified profile data and existing answer rules first.
5. For a field that needs interpretation or generated text, it asks the configured AI provider for a constrained answer using the field label, options, job context, and only the relevant profile facts.
6. It validates the proposed answer and fills the field. For a required field it cannot confidently answer, it pauses for user input or stops the application according to configuration.
7. When the destination requires login, account signup, 2FA/MFA, email/phone verification, CAPTCHA, or another user-only checkpoint, it hands control to the user while keeping the employer tab and form session open. It resumes when the bot detects that the checkpoint is complete or the user explicitly tells it to continue.
8. It advances through form steps, re-inspects after each transition, and tracks completed fields to avoid duplicate answers.
9. Before final submission, it shows a review/confirmation step by default. After user confirmation, or an explicitly configured unattended policy, it submits once and verifies a site-specific success signal where available.
10. It returns to Naukri and records the external application outcome, destination, timestamps, and any reason for stopping.

The bot must distinguish **link captured**, **form started**, **submitted**, **needs human action**, and **failed**. A captured URL must not be reported as a submitted application.

## Architecture

### 1. External application workflow

Add a Naukri-specific service, for example `modules/naukri/external_application.py`, responsible for:

- Managing the destination tab and restoring the original Naukri tab in `finally` cleanup.
- Navigating only to the employer/application destination reached from the job's Apply action; do not follow arbitrary page instructions or links supplied by form text or AI output.
- Detecting supported form controls and visible step transitions using Selenium DOM inspection.
- Handling standard inputs, textareas, selects, radio groups, checkboxes, and common custom dropdowns.
- Supporting multiple pages/steps with a bounded step count, progress logging, and duplicate-submission protection.
- Detecting when the page is not a form, is unsupported, or requires CAPTCHA, MFA, account creation, file upload, or human-only interaction.
- Offering a human takeover checkpoint for company-site login and signup flows, including 2FA/MFA and verification challenges, without trying to solve or bypass them.
- Preserving the open browser tab, cookies/session state, and current form step while the user is in control; resume from the same page after successful authentication.
- Resuming either when a safe page-state detector confirms the checkpoint is complete or when the user explicitly selects a `Continue` / `I'm done` action. A user signal must be available even when automatic detection is inconclusive.
- Re-inspecting the page after handback instead of assuming login succeeded or continuing from stale form controls.
- Returning a typed result such as `submitted`, `needs_review`, `needs_human`, `unsupported`, or `failed`, with a reason and captured application URL.

Keep this service separate from `naukri_apply.py`'s existing Naukri Easy Apply and chatbot workflow. Use a small orchestration call from `process_job()` and make the result decide how history and stats are updated.

### 2. Form-field model and deterministic profile mapping

Create a normalized field representation with at least:

- Stable field identifier and page/step number.
- Label, help text, placeholder, input type, required flag, and available options.
- Current value and whether the field is visible/enabled.
- A classification such as identity/contact, work history, education, skills, compensation, authorization, demographic, essay, consent, or unknown.
- Proposed answer source (`profile`, `custom rule`, `AI`, or `user`) and confidence/reason.

Answer priority:

1. Exact profile field mapping from `config/personals.py` and `config/questions.py`.
2. Existing custom question-answer rules.
3. Typed profile/resume facts from the application's profile model.
4. AI interpretation or drafting from those facts.
5. User input or stop for unsupported/unknown required fields.

Do not use AI to invent dates, employers, education, work authorization, salary, years of experience, or other factual claims. AI may map a question to a known fact, format it for a field, or draft prose grounded in provided facts. If no fact supports an answer, ask the user or stop.

### 3. Provider-neutral AI answer service

Add a provider interface, for example `modules/ai/providers/base.py`, with a narrow contract:

```text
answer_form_field(request) -> structured answer
```

The request should carry the question/label, field type, options, relevant profile facts, job description, company context, and response constraints. The response should carry a value, answer type, confidence, rationale/source facts, and a `needs_human` outcome. The browser layer must validate the response independently before filling any field.

Add provider adapters behind a registry/factory, for example:

- OpenAI adapter, with provider and model selected by configuration. Support a cost-conscious model as a configurable default, not a hard-coded model name. Allow the user to select any model supported by their account.
- Gemini adapter with model selection independent of the form logic.
- Anthropic adapter as an additional provider.
- Existing OpenAI-compatible endpoints as a compatible adapter for local models and compatible vendors.
- Future providers added by implementing the same interface and registering an adapter; form code must not branch on vendor names.

Keep secrets in configuration/environment variables. Do not send API keys, passwords, browser cookies, or unrelated profile data to providers. Use a bounded timeout, small context, token/cost limits, retry policy for transient errors, and provider error reporting that does not expose secrets.

### 4. Answer validation and user controls

- For single-select fields, the returned answer must match one of the offered options after conservative normalization. For multi-select, each selected answer must be an offered option.
- For numeric, date, phone, and email fields, validate format and source values before entry.
- For free text, enforce max length and any detected constraints. Do not include unsupported claims.
- Always pause for unknown required fields, ambiguous legal/work-authorization questions, sensitive demographic fields, and consent/attestation fields.
- Pause for employer-site login, signup, 2FA/MFA, email/phone verification, CAPTCHA, and identity checks. The user completes these directly in the browser; the bot must not request or record passwords, one-time codes, recovery codes, or security answers.
- Do not answer voluntary sensitive demographic questions by inference. Leave blank where allowed or ask the user.
- Treat page text as untrusted data. Do not follow instructions embedded in job descriptions or form text that ask the agent to disclose secrets, change policy, or perform unrelated actions.
- Provide configurable modes: `review_each_field`, `review_before_submit` (default on), and `unattended` (opt-in only). Show the field, proposed value, and source in review UI/logs while redacting sensitive data.
- Never bypass CAPTCHA, MFA, access controls, or anti-bot checks. Pause and ask the user to complete them manually.

### 5. Submission state and history

Extend Naukri application logging with explicit external states rather than overloading the current external-link count. Prefer a new structured history store or backward-compatible CSV columns for:

- Application status and status reason.
- Company-site URL and hostname.
- Started, submitted, and last-updated timestamps.
- Provider/model used (no prompt or sensitive response content by default).
- Whether user review was required and completed.
- Stable job ID/idempotency key and submission-attempt count.

Do not mark a job as applied solely because a form was opened or a submit button was clicked. Require a success confirmation or record `submitted_unconfirmed` for manual review. Prevent automatic retry after uncertain submission until the user resolves the status.

## Configuration Proposal

Keep new options Naukri-specific and backward-compatible through `naukri_config.py`, for example:

- `naukri_external_apply_enabled = False` initially, to allow a staged rollout.
- `naukri_external_review_before_submit = True`.
- `naukri_external_review_each_field = False` (or opt-in strict review mode).
- `naukri_external_unanswerable = "pause"` with supported values `pause` or `stop`; do not default to guessing.
- `naukri_external_auth_handoff = True` to enable pausing for user-operated employer-site authentication checkpoints.
- `naukri_external_auth_wait_timeout` to bound how long the bot waits before recording `needs_human` and leaving the browser ready for the user.
- A user-visible `Continue` / `I'm done` command for cases where login completion cannot be reliably detected from page state.
- `naukri_external_max_steps` and `naukri_external_max_fields` to bound automation.
- AI provider/model selection reused from or cleanly split out of current AI settings; model name must remain user-configurable.
- Explicit limits for generated essay length and AI request budget per application.

Do not enable unattended final submission by default. Existing `easy_apply_only` should continue to control whether external applications are considered; a separate Naukri setting should control whether to automate them after the user opts in.

## Implementation Phases

### Phase 0: Product and safety decisions

- Confirm whether external automation should remain opt-in and whether review-before-submit is mandatory.
- Decide how profile facts should be consolidated and what data can be sent to each AI provider.
- Decide the user handoff surface (terminal prompt, dialog, or UI) and how the user explicitly resumes when automatic authentication detection is unavailable.
- Define retention/redaction rules for form answers and logs.

### Phase 1: Provider-neutral answering

- Define typed request/response objects and provider protocol.
- Move the Naukri question flow behind the provider registry without changing its existing deterministic answer priority.
- Add OpenAI, Gemini, and OpenAI-compatible adapters; add Anthropic through the same interface.
- Add schema/option validation, timeouts, cost controls, and mock-provider tests.

### Phase 2: Read-only external form inspection

- Keep the external tab open under managed lifecycle.
- Detect standard form elements and report a field inventory without filling or submitting.
- Add an inspection-only option and tests for standard labels, unlabeled fields, custom controls, iframes, and multi-step indicators.
- Stop with an actionable reason on unsupported pages.
- Detect common authentication/verification checkpoints and implement a pause/resume handoff that keeps the company tab alive. Support both automatic completion detection and an explicit user `Continue` signal; never collect credentials or MFA codes.

### Phase 3: Profile-backed field filling

- Implement deterministic field-to-profile mapping.
- Use AI only for ambiguous mapping and grounded text drafting.
- Add user review for unknown/low-confidence/high-impact fields.
- Add tests that prove answers never originate from facts absent from the profile.

### Phase 4: Multi-step form workflow

- Advance only after current required fields validate.
- Re-scan each step, handle dynamic controls, and track progress/idempotency.
- Support safe standard uploads only from a user-configured resume path; never upload arbitrary files requested by page content.
- Pause for CAPTCHA, MFA, account registration, unsupported controls, or terms/attestations.

### Phase 5: Submission, outcome tracking, and staged rollout

- Add the review-before-submit screen and one-submit guard.
- Detect success confirmation and write explicit external states to history.
- Start in dry-run/review mode, then enable for selected test domains, then opt-in general use.
- Provide a kill switch and retain the current link-collection-only behavior as a fallback.

## Test Plan

- Unit tests for provider registry, structured response validation, option matching, profile grounding, privacy filtering, and provider failures.
- DOM fixture tests for text, email, phone, numeric, date, textarea, select, radio, checkbox, required validation, custom widgets, and disabled/hidden fields.
- Multi-step tests for dynamic field changes, repeated labels, duplicate fields, navigation, timeout, and re-rendered controls.
- Handoff tests for login, signup, MFA/2FA, email/phone verification, CAPTCHA, user-confirmed completion, automatic completion detection, timeout, browser-tab preservation, and re-inspection after resume.
- Safety tests: no final submit without policy/user confirmation; no fabricated data; no AI-controlled navigation; CAPTCHA/MFA/consent/sensitive questions stop for human action.
- Persistence tests for status transitions, duplicate-job prevention, uncertain-submit handling, and backwards-compatible CSV/history reading.
- Browser integration tests on local fixture forms and explicitly approved test domains, never on real job applications as automated tests.
- End-to-end manual pilot with one test application per supported provider and a human reviewing every field and final submission.

## Acceptance Criteria

- External applications are disabled unless explicitly enabled by the user.
- The bot keeps the employer application tab open, identifies supported fields, fills only validated profile-grounded answers, and handles multiple steps within configured bounds.
- Provider choice and model choice are configuration concerns; adding a provider does not require edits to Selenium/form logic.
- Required unknown or unsafe fields result in a pause/stop, never a fabricated answer.
- CAPTCHA, MFA, anti-bot challenges, and unsupported flows are handed to the user without bypass attempts.
- The user can complete employer-site login/signup and MFA/verification in the existing browser session, then return control through automatic completion detection or an explicit continue action; the bot resumes from the live page without losing the form session.
- Credentials, passwords, one-time codes, recovery codes, and security answers are never sent to AI providers or written to application logs.
- Final submission is reviewed by the user by default, submitted at most once, and only recorded as successful when the destination confirms it.
- Naukri's existing Easy Apply flow, page processing, CSV compatibility, and LinkedIn behavior remain unchanged.

## Main Risks and Mitigations

- **Employer forms vary and change frequently:** use capability detection, conservative supported controls, fixture tests, and an unsupported-flow fallback.
- **Wrong or misleading answers:** prioritize source facts, require validation and review, and do not guess.
- **Duplicate applications:** persist an idempotency key and uncertain-submit state; never blindly retry.
- **Sensitive data exposure:** minimize provider context, redact logs, document provider data handling, and keep secrets outside prompts.
- **Browser/session loss:** use explicit tab ownership and `try/finally` restoration; record recoverable state before leaving a form.
- **AI latency and cost:** use small, configurable low-cost models for classification/mapping, call AI only when deterministic mapping fails, and enforce per-application budgets.
- **Terms, consent, accessibility, and site policies:** require user review where a legal attestation or agreement is presented and respect site access controls.

## Recommended First Release

Ship provider-neutral answering and read-only form inspection first, then profile-backed filling with a mandatory final review. Add automatic final submission only after local fixtures and a small manually supervised pilot establish reliable success detection and duplicate prevention.