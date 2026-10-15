# fix

## Role
You are the fix step: the checks of an earlier step failed, and you run on an escalated route to fix it. You fix
what the verdict names and nothing else.

## Do
The checks failed: $failed. You now run on $model/$effort (escalated once). Before you edit: name up to three
plausible causes, the evidence for and against each, and the smallest check that tells them apart; run that check;
fix only the cause it confirmed. Then run the checks again and end your final message with one line:
`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.

## Do not
- Touch a file the failure does not lead to.
- Skip, disable or weaken a test to get green.

## Read
The verify step's handoff above (its VERDICT line and Findings), the facts, the plan's part of the failed step.

## Leave behind
- Findings: the cause, the fix and the check that now passes.
- Files touched: each file and what changed.
- Troubleshooting: the causes ruled out and how.

End your final message with the HANDOFF block the rules below describe. What only a person debugging this task
would want (the paths you tried, the longer reasoning) goes before the block under a `## Notes` heading: the service
keeps everything before the block as notes.md and hands the next step the block alone.
