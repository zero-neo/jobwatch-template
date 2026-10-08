# jobwatch

Finds new jobs for you every day and emails you only the ones you haven't seen.
It runs for free on GitHub, so nothing needs to be installed on your computer.
Setup takes about 20 minutes, all in your web browser.

**What you need:** a free GitHub account, a Gmail account, and a free Adzuna account.

---

## 1. Make your own private copy

1. Open this page while logged in to GitHub and click the green **Use this template** button
   (top right), then **Create a new repository**.
2. Name it `jobwatch`, choose **Private**, and click **Create repository**.

Everything below happens in *your* copy.

## 2. Tell it what you are looking for

Three files hold your settings. To edit one: click it in the file list, click the pencil icon
(top right of the file), change it, then click **Commit changes...** and **Commit changes** again.

| File | What to change |
|---|---|
| `config.yaml` | Job-title words to include and exclude, locations, English-only. The comments in the file explain each line. |
| `searches.yaml` | Which **countries** to search (e.g. `[gb]`, `[de, nl]`) and which search phrases to use. |
| `companies.yaml` | Specific companies to watch. Optional: delete the two examples if you do not want them. |

## 3. Get two free keys

**Adzuna** (the job search): sign up at <https://developer.adzuna.com>, then copy your
**Application ID** and **Application Key**.

**Gmail app password** (so it can email you): you need 2-step verification switched on for your
Google account. Then go to <https://myaccount.google.com/apppasswords>, create a password named
`jobwatch`, and copy the 16 letters (without spaces).

## 4. Save them as secrets

In your repository: **Settings → Secrets and variables → Actions → New repository secret**.
Create these four, one at a time. The name must match exactly. Paste only the value.

| Name | Value |
|---|---|
| `ADZUNA_APP_ID` | your Adzuna Application ID |
| `ADZUNA_APP_KEY` | your Adzuna Application Key |
| `SMTP_USER` | your full Gmail address |
| `SMTP_PASSWORD` | the 16-letter app password |

Emails are sent to yourself. To send them to a different address, also add a secret named
`EMAIL_TO`.

## 5. Preview, then switch it on

1. Open the **Actions** tab. If GitHub asks, click the button to enable workflows.
2. Click **jobwatch** in the left list, then **Run workflow**, tick **Preview only**, and
   click the green **Run workflow** button.
3. After a minute, click the run, then the **run** job, then open **Run jobwatch**. You will see
   the jobs it found. Too many or irrelevant? Go back to step 2 and adjust. Repeat until it looks right.
4. When happy, run it once more with **Preview only** unticked. You get an email with your first
   matches (up to 100) and it starts remembering what it has shown you.

From then on it runs by itself every day at 06:00 UTC and emails you only new jobs.
No email on a given day just means nothing new was found.

To change the time, edit `.github/workflows/jobwatch.yml` and change the `cron` line.

## Optional: also keep a Google Sheet

You get a spreadsheet of every job, with Status and Notes columns you can fill in.
This needs a free Google Cloud service account, so skip it unless you want it.

1. At <https://console.cloud.google.com> create a project and enable the **Google Sheets API**.
2. Create a **service account**, then under its **Keys** tab add a **JSON** key. A file downloads.
3. Create a blank Google Sheet and **share it (Editor)** with the service account's email address
   (it looks like `name@project.iam.gserviceaccount.com`).
4. Add two more secrets: `GOOGLE_SERVICE_ACCOUNT_JSON` (open the downloaded file in a text editor
   and paste **all** of its contents) and `JOBWATCH_SHEET_ID` (the long text in the Sheet's web
   address between `/d/` and `/edit`).

Never put the JSON file or any key into your repository files. Only into secrets.

## If something goes wrong

| What you see | What to do |
|---|---|
| Run is red, log says `Adzuna: set ADZUNA_APP_ID...` | A secret is missing or misspelled (step 4). |
| `Email failed ... authentication` | Wrong Gmail app password, or 2-step verification is off. |
| `Email not configured` | `SMTP_USER` or `SMTP_PASSWORD` is missing or misspelled. |
| `HTTP 404` for a company | That company's `slug` in `companies.yaml` is wrong. Check it opens in a browser. |
| Run fails on the **Save state** step | **Settings → Actions → General → Workflow permissions → Read and write permissions**, then re-run. |
| Far too many or irrelevant jobs | Add words to `title_exclude` in `config.yaml`. |
| No emails for days | Open the Actions tab and check that the daily runs are green. GitHub also emails you when a run fails. |

Your settings, your secrets and the list of jobs already shown to you stay in your private copy.
