# Plan 54: atomic Console saves with open metadata readers

Status: implemented and validated 2026-11-07. Plan 52 Task 7 is not started.

Scope: fix the Windows replacement collision separately from plan 52. No task format change, migration,
in-place overwrite, save retry loop, database, UI change or CLI configuration edit. PLAN.md and plans/53-build/
belong to another chat and stay untouched and unstaged.

## Evidence and contract

- Listary's open task.json handle overlapped a denied replacement in the earlier elevated FileIO trace.
- After Fred excluded the Console data folder from search, a scratch home under that folder still failed on
  save 309 with Listary running. With its app and hook hosts closed, 10,000 saves passed in 228.727 seconds.
  ListaryService.exe remained running. Both scratch homes were removed and Listary was restored.
- Listary 7.1's search exclusions hide results while indexing continues. Installed version: 7.1.0.47.
- A controlled metadata reader without delete sharing blocks os.replace. A scratch prototype successfully used
  SetFileInformationByHandle(FileRenameInfoEx) with REPLACE_IF_EXISTS and POSIX_SEMANTICS while that reader stayed
  open. New opens saw the new file after the rename handle closed.

Keep each save whole: write and flush a separate temporary file, replace once, then close the writer. Existing
readers may finish reading the old file; later opens read the new file. Genuine access, disk and write errors
still propagate, preserving the old destination. No permission bypass or read-only override. An incompatible
content reader can still refuse replacement; the native mode handles the metadata-reader collision, not every
possible file lock. A regression test keeps that refusal and verifies preservation of the old bytes.

## Implementation

1. Tests first: task saves and the other existing atomic Console writers under a held metadata handle; an old
   compatible content reader; reserved temporary file; write/rename failure preservation and cleanup;
   concurrent writers; embedded NUL rejection before any file is opened. Incompatible content readers still
   refuse safely.
2. Reuse paths.write_text_atomic as the shared entry point. On Windows, create the temporary file with write
   and DELETE access and keep that handle through writing and renaming, avoiding a second open for DELETE
   after a metadata reader appears on the temporary file. Keep ordinary os.replace as the normal path. Only Windows errors
   5 and 32 admit one native FileRenameInfoEx operation with the documented open-destination flags. There is no
   sleep, rewriting or replacement retry loop. If the native mode is explicitly unsupported, propagate the
   original failure, retaining the previous behavior on those filesystems. Other native errors propagate.
3. Route tasks.save, task message attachments, config, window, usage and kind-file atomic saves through that
   helper. Preserve their existing locks, validation, JSON/text formatting and error responses. Other platforms
   retain os.replace. The standalone install_hooks.py stays unchanged.
4. Focused tests for these writers and their server/message/supervisor callers. Run a monitored 10,000-save
   scratch probe and the full background suite with Listary's app, both hook hosts and service running. Read
   completed output and record counts, failures, errors, warnings and durations. No real task data is used.
5. Record results here and make a separate persistence-fix commit. Do not amend plan 52 Task 6 or start Task 7.

References: [Windows rename flags](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information),
[SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle),
[Listary exclusion clarification](https://discussion.listary.com/t/listary-7-1-beta-is-here-rewritten-in-rust-up-to-4x-faster-34-less-memory-oct-8/10325).

## Results

Tests were added first. The final writer set (test_atomic, test_paths, test_tasks, test_usage, test_kinds)
passed 194 tests in 3.289 seconds with zero failures or errors. The server, supervisor-server, task-message
and web focused modules passed 506 tests in 547.053 seconds with zero failures or errors.

The closing full background suite passed 1167 tests in 600.960 seconds, exit 0, with zero failures, errors
or warnings. A preliminary full run was stopped before completion to add the embedded-NUL validation
regression; no completed count is claimed for that run. The regression first demonstrated that the native
LPCWSTR boundary could truncate a different scratch filename, then passed after rejection was added before
any file or directory is opened. The old destination stays unchanged on encoding and native errors.

With Listary running, the real tasks.save path completed 10,000 scratch saves in 244.399 seconds. Every saved
revision was read back and checked. Its 143 process checks found Listary.exe, ListaryHookHost32.exe,
ListaryHookHost64.exe and ListaryService.exe running; the temporary Console home was removed afterward.
This is the same probe that failed on save 309 before the fix.

The separate monitoring loop completed 1448 process polls, including 612 from the closing suite's start
through monitor shutdown, with zero missing-component polls. All four Listary processes remained running
with their original process ids. One PowerShell monitor JSON update encountered a sharing error; polling
continued, and the final summary retained all 1448 checks and zero missing components. This was a monitor
log update, not a Console save or a test-suite warning.

Diff whitespace checks passed. No real task data or CLI configuration was changed. The shared writer now
covers task state, task message attachments, config, window state, usage, kind-file saves and the existing
draft/handoff callers. Existing locks, validation, payload formats and error handlers are retained. No kind
template changed, so Models page Reset to repo copy is unnecessary. PLAN.md and plans/53-build/ remain
untouched and unstaged.

The running Console was not interrupted; restart it when idle to load the code. Incompatible content locks,
read-only destinations and genuine write failures still refuse safely. Other platforms retain os.replace;
Linux/macOS execution was not checked on this Windows machine. No past failed save is replayed or repaired.
