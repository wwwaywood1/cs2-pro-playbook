#!/usr/bin/env python3
"""Start a long job that keeps running after the shell that started it has gone.

    python3 scripts/run_detached.py _sync/job.log bash _sync/job.sh

The job gets its own session (no controlling terminal), stdin from /dev/null and its output
appended to the log; the command returns at once and prints the job's process id.
Background jobs started with plain ``nohup cmd &`` from a Codex command on the Mac were
frozen as soon as that command finished (an importer and its bsdtar stopped mid-file and
never resumed); a job started this way is not tied to that shell or terminal.
"""
import subprocess
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    log, cmd = argv[0], argv[1:]
    with open(log, "ab", buffering=0) as out:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True)
    print(proc.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
