# Submission guide, early October 2026 target

This is the step-by-step plan to get ConfusionMapper published before your admissions deadlines.

Two outputs to aim for, in parallel:

1. **EdArXiv preprint** (instant, free, no endorsement, no fee)
2. **PeerJ Computer Science peer-reviewed paper** (~10 weeks, free if fee waiver approved)

## Step 1 (today), Push the latest paper and code to GitHub

```bash
cd D:\Confusion-Mapper
git add -A
git commit -m "docs(paper): pivot to academic format for arXiv + PeerJ submission; affiliation now Independent Researcher"
git push origin main
```

After the push, your Actions tab will rebuild the paper PDF (the old JOSS workflow still works for paper-joss.md if you want a JOSS-style preview).

## Step 2 (today, 30 min), Generate the PDF for submission

Install pandoc and a TeX distribution on Windows:

1. Pandoc: <https://pandoc.org/installing.html>
2. MiKTeX (Windows TeX): <https://miktex.org/download>

Then from `D:\Confusion-Mapper`:

```bash
pandoc paper.md ^
  --bibliography=paper.bib ^
  --citeproc ^
  --pdf-engine=xelatex ^
  --variable=geometry:margin=1in ^
  --variable=fontsize:11pt ^
  -o paper.pdf
```

(Use `^` for line breaks on Windows Command Prompt, or `\` on PowerShell or Git Bash.)

If pandoc fails on a missing package, MiKTeX will offer to install it automatically.

Open `paper.pdf` and skim: title page, abstract, comparison table, references should all render cleanly.

## Step 3 (today, 30 min), Submit to EdArXiv

EdArXiv accepts preprints without endorsement, runs on the same OSF infrastructure you already use for your CFI preprint, and gives you a permanent DOI within ~24 hours.

1. Go to <https://edarxiv.org/>
2. Click "Add a preprint"
3. Sign in with your existing OSF account (the one that owns osf.io/ck6nj and the CFI preprint at 10.35542/osf.io/cr53e_v1).
4. Upload `paper.pdf`.
5. Fill in:
   - **Title:** ConfusionMapper: A Human-AI Hybrid Inter-Rater Reliability Tool for Cognitive Error Taxonomy Classification in Multiple-Choice Questions
   - **Abstract:** copy from paper.md (between `abstract:` and the closing `---`)
   - **Authors:** Manik Maurya (link your ORCID 0009-0005-3554-693X)
   - **Subject:** Education, Educational assessment, Methodology
   - **License:** CC-BY 4.0
   - **Tags:** inter-rater reliability, Cohen's kappa, educational assessment, multiple-choice questions, distractor classification, Krippendorff's alpha, prompt refinement
   - **Funding / conflicts:** None
   - **Supplemental materials:** link to GitHub repo and Zenodo DOI
6. Submit.

You receive a permanent EdArXiv DOI within 24-48 hours. You can now write "Maurya, M. (2026). ConfusionMapper... EdArXiv. https://doi.org/XX.XXXXX/osf.io/XXXXX" in your applications.

## Step 4 (today), Send the fee waiver email to PeerJ

Send the email in `submission/fee_waiver_email.md` to `fees@peerj.com` from `manikmaurya.in@gmail.com`. Wait 2-5 business days for a reply. PeerJ historically grants these for independent researchers from lower-income countries.

While you wait for the waiver decision, do steps 5 and 6.

## Step 5 (this week), Create a PeerJ account and start the submission

1. Go to <https://peerj.com/computer-science/submit/>
2. Click "Sign up" and create an account with `manikmaurya.in@gmail.com`. Verify your email.
3. Link your ORCID 0009-0005-3554-693X on your profile page.
4. Click "Submit a new article."
5. Pick:
   - **Article type:** Software Tools (short-format track)
   - **Section:** Software Engineering or Educational Technology (either fits)
6. The submission form will walk you through 9 steps. Save and continue between sessions.

## Step 6 (this week), Complete the PeerJ submission form

You will be asked for:

| Field | Value |
|---|---|
| Title | ConfusionMapper: A Human-AI Hybrid Inter-Rater Reliability Tool for Cognitive Error Taxonomy Classification in Multiple-Choice Questions |
| Authors | Manik Maurya (sole author) |
| Affiliation | Independent Researcher, Kanpur, India |
| ORCID | 0009-0005-3554-693X |
| Abstract | copy from the YAML block of paper.md |
| Keywords | inter-rater reliability; Cohen's kappa; educational assessment; multiple-choice questions; distractor classification; cognitive science; human-AI collaboration |
| Funding statement | This research received no external funding. |
| Competing interests | The author declares no competing interests. |
| Data availability | Source code and worked example archived at https://doi.org/10.5281/zenodo.20807432 and developed at https://github.com/Manik-Maurya/Confusion-Mapper |
| Manuscript file | upload paper.pdf |
| Cover letter | paste contents of `submission/cover_letter.md` |
| Supplemental files | paper.bib, paper.md source, case_study/results/REPORT.md (optional but useful) |

When asked about preprint, mention the EdArXiv preprint you just posted.

## Step 7, Submit, then track

Click submit. PeerJ assigns an editor within 1-2 weeks. The editor invites 2-3 reviewers. Reviews come back in 4-8 weeks. You either get accepted, asked for minor revisions, or asked for major revisions. Total median time from submission to acceptance for Software Tools is around 10 weeks.

## Step 8 (during review), Build the impact evidence reviewers will look for

Reviewers and the editor will check the GitHub repo for signs of life. Between submission and decision, do these:

- Cut at least one v1.1.0 release with a small feature add (open the GitHub release page, click "Draft a new release")
- Open 2-3 GitHub issues yourself describing planned features (e.g. "Add support for Cohen's kappa with missing data", "Add SVG export of confusion matrix")
- Post the tool on the educational-research subreddit, methodology Twitter, and any cognitive-science Slack or Discord you can find
- Email the EdArXiv preprint link to 5-10 researchers who work on misconception taxonomies; ask if they would try it on their data
- Get at least one outside person to star, fork, or open an issue on the repo

The reviewer auto-bot at JOSS flagged 0 stars, 0 issues, 0 PRs as a red flag. PeerJ reviewers are human, but they look at the same signals. Even modest activity helps.

## Step 9 (early September), Respond to reviewer comments

Most submissions get "minor revisions" or "major revisions" rather than outright acceptance on the first round. Respond to every comment in a separate response letter, even if you disagree (then politely explain why). Resubmit within 4 weeks of receiving the comments to keep the timeline tight.

## Step 10 (early October), Acceptance

PeerJ publishes accepted papers within 1-2 weeks of acceptance. You will have:

- A PeerJ Computer Science paper with DOI, indexed in Scopus, Web of Science, and PubMed
- An EdArXiv preprint (filed in step 3)
- The Zenodo software archive (already at 10.5281/zenodo.20807432)
- A live PyPI package
- An active GitHub repo with releases and outside engagement

That bundle is significantly stronger than a single JOSS paper would have been.

## After October, Resubmit to JOSS in December

By December 1, 2026 you meet the 6-month rule. Your paper-joss.md backup is ready. The PeerJ publication and EdArXiv preprint will satisfy the "demonstrable impact" criterion that blocked you in June. Resubmit at <https://joss.theoj.org/papers/new>.

## What's in this submission folder

- `cover_letter.md`, paste into PeerJ's cover-letter field
- `fee_waiver_email.md`, send to fees@peerj.com BEFORE submitting
- `SUBMISSION_GUIDE.md`, this file
