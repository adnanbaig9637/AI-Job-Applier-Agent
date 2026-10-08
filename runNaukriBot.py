'''
Naukri job application automation.

Run with:
    python runNaukriBot.py

This is the Naukri sibling of `runAiBot.py`. It reuses the browser setup,
helpers, AI providers and shared profile configuration, with optional Naukri
search preferences in `config/naukri_filter_config.py`, and follows this flow:

  Launch Chrome -> open Naukri -> detect login -> let the human log in if
  needed -> search using the configured criteria -> screen each job -> apply ->
  log everything to CSV.

`runAiBot.py` (LinkedIn) is not imported or modified by this file in any way.
'''

import os
from datetime import datetime
from random import choice

import pyautogui
from selenium.common.exceptions import NoSuchWindowException, WebDriverException

from config.questions import default_resume_path
from config.secrets import use_AI, ai_provider
from config.settings import (
    run_in_background, run_non_stop, alternate_sortby, cycle_date_posted,
    stop_date_cycle_at_24hr, logs_folder_path,
)

from modules.open_chrome import driver, wait
from modules.helpers import print_lg, buffer, sleep, critical_error_log, make_directories
from modules.validator import validate_config
from modules import relevance
from modules.naukri import naukri_config, naukri_apply
from modules.naukri.naukri_dialogs import alert
from modules.naukri.naukri_login import ensure_logged_in

if use_AI:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_close_openai_client
    from modules.ai.deepseekConnections import deepseek_create_client
    from modules.ai.geminiConnections import gemini_create_client


pyautogui.FAILSAFE = False

# Same rule as runAiBot.py: a background run can't show dialogs, so it can't loop forever.
_run_non_stop = False if run_in_background else run_non_stop

aiClient = None
naukri_tab = None

# The run loop mutates these locally, exactly like the LinkedIn bot does.
current_date_posted = naukri_config.get_date_posted()
current_sort_by = naukri_config.get_sort_by()


def create_ai_client():
    '''Creates the configured AI client, reusing the existing provider modules.'''
    if not use_AI:
        return None
    try:
        if ai_provider == "openai":
            return ai_create_openai_client()
        if ai_provider == "deepseek":
            return deepseek_create_client()
        if ai_provider == "gemini":
            return gemini_create_client()
        print_lg(f'Unknown ai_provider "{ai_provider}", continuing without AI.')
    except Exception as e:
        print_lg("Failed to create the AI client, continuing without AI.", e)
    return None


def close_ai_client(client) -> None:
    '''Closes the AI client the same way `runAiBot.py` does.'''
    if not (use_AI and client):
        return
    try:
        if ai_provider.lower() in ("openai", "deepseek"):
            ai_close_openai_client(client)
        # Gemini's client does not need to be closed.
        print_lg(f"Closed {ai_provider} AI client.")
    except Exception as e:
        print_lg("Failed to close AI client:", e)


def run(total_runs: int) -> int:
    '''One full pass over every configured search term.'''
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for Naukri jobs posted within '{current_date_posted}' "
             f"and sorting them by '{current_sort_by}'")
    naukri_apply.apply_to_jobs(driver, wait, naukri_config.get_search_terms(), aiClient,
                               sort_by=current_sort_by, date_posted=current_date_posted)
    print_lg("########################################################################################################################\n")
    # Only cool down between cycles. A single run has nothing left to wait for.
    if _run_non_stop:
        print_lg("Sleeping for 10 min...")
        sleep(300)
        print_lg("Few more min... Gonna start with in next 5 min...")
        sleep(300)
        buffer(3)
    return total_runs + 1


def main() -> None:
    global aiClient, naukri_tab, current_date_posted, current_sort_by
    total_runs = 1
    alert_title = "Error Occurred. Closing Browser!"

    try:
        validate_config()
        make_directories([
            naukri_config.naukri_file_name,
            naukri_config.naukri_failed_file_name,
            logs_folder_path + "/screenshots",
        ])

        print_lg("\n>>>> Naukri job application bot <<<<")
        print_lg("Resolved Naukri search configuration:")
        print_lg(naukri_config.describe())
        print_lg("Job relevance rules:")
        print_lg(relevance.describe())

        if not os.path.exists(default_resume_path):
            print_lg(f'Your default resume "{default_resume_path}" is missing. Naukri applies with the '
                     f'resume already uploaded to your Naukri profile, so this only affects LinkedIn.')

        # Login to Naukri
        ensure_logged_in(driver, wait)
        naukri_tab = driver.current_window_handle

        aiClient = create_ai_client()

        driver.switch_to.window(naukri_tab)
        total_runs = run(total_runs)
        while _run_non_stop:
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                if current_date_posted in date_options:
                    index = date_options.index(current_date_posted)
                    if stop_date_cycle_at_24hr:
                        current_date_posted = date_options[index + 1] if index + 1 < len(date_options) else date_options[-1]
                    else:
                        current_date_posted = date_options[(index + 1) % len(date_options)]
            if alternate_sortby:
                current_sort_by = "Most recent" if current_sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                current_sort_by = "Most recent" if current_sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)

    except (NoSuchWindowException, WebDriverException) as e:
        print_lg("Browser window closed or session is invalid. Exiting.", e)
    except Exception as e:
        critical_error_log("In Naukri Applier Main", e)
        alert(str(e), alert_title)
    finally:
        applied = naukri_apply.stats["applied"]
        external = naukri_apply.stats["external"]
        failed = naukri_apply.stats["failed"]
        skipped = naukri_apply.stats["skipped"]
        search_failed = naukri_apply.stats.get("search_failed", 0)
        summary = ("Total runs: {}\nJobs applied on Naukri: {}\nExternal job links collected: {}\n"
                   "Total applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n"
                   "Failed searches: {}\n"
                   ).format(total_runs, applied, external, applied + external, failed, skipped, search_failed)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs applied on Naukri:         {}".format(applied))
        print_lg("External job links collected:   {}".format(external))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(applied + external))
        print_lg("\nFailed jobs:                    {}".format(failed))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skipped))
        print_lg("Failed searches:               {}\n".format(search_failed))
        if naukri_apply.skip_reasons:
            print_lg("Why jobs were skipped (most common first):")
            for reason, count in sorted(naukri_apply.skip_reasons.items(),
                                        key=lambda item: item[1], reverse=True):
                print_lg(f"  {count:>4}  {reason}")
            print_lg("")
        if naukri_apply.randomly_answered_questions:
            print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(
                ";\n".join(str(question) for question in naukri_apply.randomly_answered_questions)))

        quote = choice([
            "Never quit. You're one step closer than before. - Sai Vignesh Golla",
            "All the best with your future interviews, you've got this. - Sai Vignesh Golla",
            "Keep up with the progress. You got this. - Sai Vignesh Golla",
            "If you're tired, learn to take rest but never give up. - Sai Vignesh Golla",
            "Success is not final, failure is not fatal, It is the courage to continue that counts. - Winston Churchill",
            "Opportunities don't happen, you create them. - Chris Grosser",
        ])
        alert(f"{quote}\n\n\nSummary:\n{summary}", "Exiting..")
        print_lg("Closing the browser...")

        close_ai_client(aiClient)
        try:
            if driver:
                driver.quit()
        except WebDriverException as e:
            print_lg("Browser already closed.", e)
        except Exception as e:
            critical_error_log("When quitting...", e)


if __name__ == "__main__":
    main()
