---
name: seed-fault
description: Deliberately introduce a specified pipeline fault, capture verification evidence, repair the fault, and confirm recovery.
allowed-tools: Read, Edit, Bash(python -m pytest*), Bash(make*), Bash(git status*), Bash(git diff*), Bash(shasum*)
---

# Working tree at start

!`git status --short`

# Seeding a fault: $ARGUMENTS

This is a controlled fault-injection experiment. The point is honest
evidence about what the verification suite and the PostToolUse hook do and
do not catch, so report what happens, not what you expect to happen. Work
in this order.

1. **Check the baseline.** Run `git status --short` and `make test`. If
   `make test` is not green, stop and report it; a fault seeded on a failing
   baseline proves nothing. If the file you would edit already has
   uncommitted changes, stop and say so. Uncommitted changes elsewhere (for
   example `.claude/settings.json`) are not yours: leave them alone, and
   note them. Record the passing test count and time, and the SHA-256 of
   `data/raw/bike_daily.csv`.

2. **Identify the smallest edit** that introduces the fault in
   `$ARGUMENTS`: one line or one block, one function, no collateral
   changes. Write down the exact original code and the exact faulty code
   before you touch anything. If the request needs a change to a test,
   `data/raw/`, or hook configuration, stop and say that it is out of scope.

3. **Introduce it with the Edit tool**, never with a shell command, so the
   PostToolUse hook runs. The hook (`.claude/hooks/check_leakage.sh`) only
   acts on edits to `src/**/*.py`, and then re-runs
   `tests/test_leakage.py`. Do not change what the hook does or how it is
   configured.

4. **Capture the evidence.** Copy the exact code change, the hook's
   stderr verbatim, and the failing test output verbatim, including expected
   and obtained values where the assertion shows them. Do not summarise
   output and do not tidy it up. If the hook printed nothing, record that
   it printed nothing, then run the relevant tests yourself
   (`python -m pytest tests/test_leakage.py -q`, or `make test` for faults
   outside that file) and capture that output. Keep the original passing
   run's output as well.

5. **If no test fails, report the coverage gap.** State which behaviour
   changed, which tests ran, and that all of them passed. Never fabricate
   or imply a failure, and do not add or change tests unless the user then
   asks. Still pause at step 6, then do steps 7 to 9.

6. **Pause for approval. This step is mandatory.** After steps 4 and 5,
   stop and do not repair the fault. Show the user the exact code change,
   the hook stderr, and the test output (or the coverage gap), and say
   plainly that the faulty code is still in the working tree. Ask whether
   to repair, then wait for an explicit reply. Silence, an unrelated
   message, or approval given earlier for another step is not approval. Do
   not start step 7 until the user approves. If the user asks for something
   else first, such as recording the failure or adding a test, do that and
   keep waiting; the fault stays in place until they approve the repair.

7. **Restore the original code** with the Edit tool, exactly as recorded in
   step 2. Count the agent repair turns: a turn is one assistant turn
   spent restoring the code after approval. One Edit followed by a passing
   `make test` is 1 turn. The pause is not a repair turn. Count the turn
   spent seeding or writing a test separately, and say it was not repair.

8. **Verify recovery.** Run `make test` and show the output. Run
   `git diff -- <edited file>` and confirm it is empty, and re-run
   `shasum -a 256 data/raw/bike_daily.csv` and confirm it matches the
   step 1 hash. If anything differs, report it instead of claiming
   recovery.

9. **Append the evidence to `docs/SEEDED_FAULTS.md`** as a new
   `## Fault N: <short title>` section, using the next unused number and the
   structure of the existing sections. Include, in order: the file and
   function; the exact original and faulty code; the hook stderr verbatim
   (or that there was none); the failing test output, or the coverage gap;
   the passing baseline and repair outputs; the repair-turn count; why the
   fault matters; and that the hook detects an edit but does not undo it.
   Only record what happened. Say so where something was not run, or where
   output was carried over from an earlier step rather than re-run.

Never modify raw data, weaken or delete existing tests, bypass or change
permissions, or disable or edit hooks. If a tool call is denied, report the
exact denial and stop rather than working around it.

Do not commit. Leave `docs/SEEDED_FAULTS.md` and any other changes in the
working tree and tell the user what is uncommitted. Do not stage
`.claude/settings.json`.
