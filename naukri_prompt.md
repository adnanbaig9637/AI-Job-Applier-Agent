You are working on an existing **LinkedIn Job Application Automation** project.

### Current LinkedIn Behavior

The project currently works correctly when running:

```bash
python runAiBot.py
```

The automation:

1. Launches Chrome.
2. Navigates to LinkedIn.
3. Detects whether the user is already logged in.
4. If not logged in, asks the human to complete the LinkedIn login.
5. Once logged in, reads the existing job-related configuration.
6. Searches for relevant jobs based on the configured criteria.
7. Applies to the required jobs automatically.
8. Current linkedin implementation works With AI or Without AI. So new naukri also should work the same way.

**Do not modify or break any of this existing LinkedIn functionality.**

---

### Task

Your task is to **review the existing codebase and implement a new Naukri job application automation**, following the same architecture, workflow, configuration, and user experience as the existing LinkedIn automation wherever applicable.

Before making changes:

* Inspect the complete existing project structure.
* Understand how `runAiBot.py` starts the automation.
* Understand how LinkedIn automation is implemented.
* Identify how job configurations are currently defined and consumed.
* Identify reusable components that can be shared between LinkedIn and Naukri.
* Understand the existing login, job search, filtering, application, logging, error handling, and browser automation flow.

### Naukri Automation Requirements

Implement Naukri automation with the following behavior:

1. Launch Chrome.
2. Navigate to Naukri.
3. Detect whether the user is logged in.
4. If not logged in, pause and allow the human to complete login.
5. Continue automatically after login.
6. Use the **same existing job configuration/settings** that are currently used for LinkedIn wherever applicable.
7. Search for jobs on Naukri based on those configurations.
8. Apply to matching jobs using Naukri's application flow.
9. Handle pages/forms/questions that require human interaction in the same general way the existing LinkedIn automation handles them.
10. Add proper logging so it is clear which jobs were found, skipped, attempted, successfully applied, or failed.
11. Handle common Naukri-specific variations gracefully instead of relying on a single rigid page structure.

### Important: Preserve Existing Functionality

**This is critical.**

Do NOT rewrite or unnecessarily refactor the existing LinkedIn automation.

The existing LinkedIn flow is working and must continue working exactly as it does today.

Follow these principles:

* Reuse existing utilities/components where appropriate.
* Keep LinkedIn-specific logic isolated from Naukri-specific logic.
* Avoid changing existing LinkedIn selectors or workflows unless absolutely necessary.
* Do not remove existing functionality.
* Do not change existing configuration behavior in a breaking way.
* Maintain backward compatibility with the current `runAiBot.py` execution.
* If a shared component needs modification, make sure the change remains compatible with LinkedIn.

### Configuration

The current project already contains configuration related to:

* Job titles
* Locations
* Experience
* Job filters
* Application preferences
* Other job-search/application settings

**Do not create a completely separate configuration system for Naukri unless technically necessary.**

First understand the existing configuration and make Naukri consume the same configuration wherever possible.

If a Naukri-specific setting is required, add it in a backward-compatible way.

### Implementation Approach

Do not immediately start changing code.

First:

1. Explore and understand the existing codebase.
2. Trace the complete LinkedIn execution flow from `runAiBot.py`.
3. Identify reusable components.
4. Identify LinkedIn-specific components that should not be reused directly.
5. Design the Naukri implementation to fit naturally into the current architecture.
6. Then implement the changes incrementally.

After implementation:

* Run/validate the existing LinkedIn flow to ensure it has not been broken.
* Validate the new Naukri flow.
* Fix any issues discovered during testing.
* Keep the implementation clean and maintainable.

### Final Goal

The final project should support **both LinkedIn and Naukri job application automation** while preserving the existing LinkedIn behavior.

The existing LinkedIn automation must continue to work exactly as before, and Naukri should be added as a new supported job platform using the existing project configuration and architecture as much as possible.

**Start by inspecting the codebase and explaining the current LinkedIn architecture and the implementation plan for Naukri. Then proceed with the implementation.**
