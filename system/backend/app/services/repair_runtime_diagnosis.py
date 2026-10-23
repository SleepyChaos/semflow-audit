"""Distinguish verified candidate name failures from unproven environments."""


def candidate_runtime_errors(suite, pairs, workspace):
    errors = []
    for case in suite.cases:
        observations = [
            pair["after"].get("cases", {}).get(case.name, {}) for pair in pairs
        ]
        if len(observations) != 2 or any(
            row.get("status") != "error" for row in observations
        ):
            continue
        kinds = [row.get("exception_type") for row in observations]
        location = observations[0].get("exception_file")
        line = observations[0].get("exception_line")
        if not isinstance(location, str) or type(line) is not int or line < 1:
            continue
        name = location.removeprefix("/workspace/")
        source = (workspace / name).resolve()
        if (
            not source.is_relative_to(workspace.resolve())
            or not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > 1024 * 1024
        ):
            continue
        if any(
            row.get("exception_file") != location or row.get("exception_line") != line
            for row in observations
        ):
            continue
        try:
            if line > len(source.read_text().splitlines()):
                continue
        except UnicodeError:
            continue
        # Baseline calibration and complete execution are checked by the caller.
        # Do not treat imports, dependency versions or unknown exceptions as a
        # request to rewrite business code. A ValueError raised inside candidate
        # code can also escape a previously calibrated HTTP request; callers
        # filter these observations to cases with a known original baseline.
        if len(set(kinds)) == 1 and kinds[0] in {
            "NameError",
            "UnboundLocalError",
            "ValueError",
        }:
            errors.append(
                {
                    "test": case.name,
                    "candidate_file": name,
                    "candidate_line": line,
                    "exception_type": kinds[0],
                    "message": observations[0].get("exception_message", "")[:500],
                    "meaning": "Actual repeated candidate execution error after calibrated baseline; not a security assertion pass",
                }
            )
    return errors
