"""Reading and validating a campaign's config.

A campaign is one goal, one directory, one budget and one approval (design.md
section 1). `campaign.toml` is the only place those live, so the runner reads
this module and decides nothing for itself.

Validation is strict and happens on load. The alternative is a mistyped noise
bound or budget found out after a day of machine time has been spent against
it, and every error names the key it came from so the fix is obvious.

Approval is deliberately not part of loading. The file loads without one, so a
campaign that is still being written can still be inspected, and
`require_approval` is what the runner calls before it launches anything (R33).
"""

import dataclasses
import datetime
import os
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    try:
        import tomli as tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - environment gap
        raise ImportError(
            "reading campaign.toml needs Python 3.11 or the tomli package"
        ) from exc


class CampaignProblem(Exception):
    """The campaign file needs a person, not a guess."""


class ApprovalMissing(CampaignProblem):
    """No usable approval record, so nothing may be launched.

    Its own type because it is the one refusal the caller reports plainly
    rather than as a broken config: the file is fine, the permission is not.
    """


# Window names are the same grammar make_window.py accepts, on a 0.1 ms grid.
# Checking them here means a typo fails before a case is generated rather than
# after the generator has already cut a seed.
WINDOW = re.compile(r"^test\d+_\d+\.\d-\d+\.\dms$")

# Every table the runner reads. Listed so a missing one is reported by name
# instead of surfacing later as a KeyError somewhere in the loop.
REQUIRED_TABLES = (
    "campaign",
    "build",
    "baseline",
    "search",
    "limits",
    "budget",
    "disk",
    "correctness",
    "machine",
)


@dataclasses.dataclass(frozen=True)
class Rung:
    """One fidelity level: windows of similar cost, judged to one bound."""

    number: int
    windows: tuple
    noise_bound: float
    repeats: int


@dataclasses.dataclass(frozen=True)
class Approval:
    """Who authorised this campaign, when, and for how much machine time."""

    approved_by: str
    approved_on: str
    slot_hours: float
    scope: str


@dataclasses.dataclass(frozen=True)
class Campaign:
    """A validated campaign config. Nothing here is a path to this machine."""

    path: str
    name: str
    goal: str
    test: str
    parent: str
    epoch: str
    build: dict
    recipe: str
    search_space: str
    rungs: tuple
    limits: dict
    slot_hours: float
    disk: dict
    correctness: dict
    machine: dict
    approval: object = None
    # Why the approval record cannot be used, when there is one but it is
    # incomplete. Kept rather than raised, so a campaign still being written
    # can be read.
    approval_problem: str = ""

    def windows(self):
        """Every window the ladder names, rung order preserved."""

        return [w for rung in self.rungs for w in rung.windows]

    def rung_for(self, window):
        """The rung a window belongs to, or None if the ladder omits it."""

        for rung in self.rungs:
            if window in rung.windows:
                return rung
        return None

    def require_approval(self):
        """Raise unless this campaign may launch. Returns the approval."""

        if self.approval_problem:
            raise ApprovalMissing(
                f"{self.path}: {self.approval_problem}, so no run may be"
                " launched (R33)."
            )
        if self.approval is None:
            raise ApprovalMissing(
                f"{self.path} has no [approval] table, and the runner refuses to"
                " start on a campaign the user has not approved (R33)."
            )
        if self.approval.slot_hours + 1e-9 < self.slot_hours:
            raise ApprovalMissing(
                f"{self.path}: [budget] slot_hours is {self.slot_hours} but only"
                f" {self.approval.slot_hours} were approved, so the budget"
                " exceeds its approval."
            )
        return self.approval


# --- checking --------------------------------------------------------------
#
# Each checker takes the dotted key it is checking so the message can name it.
# A campaign file is read by a person and written by a person, and "value out
# of range" without the key is a message that makes them go looking.


def _table(data, name, where):
    value = data.get(name)
    if value is None:
        raise CampaignProblem(f"{where}: [{name}] is missing.")
    if not isinstance(value, dict):
        raise CampaignProblem(f"{where}: [{name}] must be a table.")
    return value


def _text(table, key, where, allow_empty=False):
    value = table.get(key)
    if value is None:
        raise CampaignProblem(f"{where}: {key} is missing.")
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise CampaignProblem(f"{where}: {key} must be a non-empty string.")
    return value


def _number(table, key, where, low=None, high=None):
    value = table.get(key)
    if value is None:
        raise CampaignProblem(f"{where}: {key} is missing.")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CampaignProblem(f"{where}: {key} must be a number, not {value!r}.")
    if low is not None and value < low:
        raise CampaignProblem(f"{where}: {key} must be at least {low}, not {value!r}.")
    if high is not None and value > high:
        raise CampaignProblem(f"{where}: {key} must be at most {high}, not {value!r}.")
    return float(value)


def _whole(table, key, where, low=1):
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CampaignProblem(f"{where}: {key} must be a whole number, not {value!r}.")
    if value < low:
        raise CampaignProblem(f"{where}: {key} must be at least {low}, not {value!r}.")
    return value


def _list_of_text(table, key, where, allow_empty=False):
    value = table.get(key, [] if allow_empty else None)
    if not isinstance(value, list):
        raise CampaignProblem(f"{where}: {key} must be a list of strings.")
    if not value and not allow_empty:
        raise CampaignProblem(f"{where}: {key} must name at least one entry.")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise CampaignProblem(
                f"{where}: every entry of {key} must be a non-empty string,"
                f" and {item!r} is not."
            )
    return list(value)


def _rungs(data, where):
    ladder = data.get("ladder")
    if not isinstance(ladder, list) or not ladder:
        raise CampaignProblem(
            f"{where}: the ladder is missing; declare at least one [[ladder]] rung."
        )

    rungs, seen = [], set()
    for position, entry in enumerate(ladder):
        at = f"{where}: [[ladder]] entry {position + 1}"
        if not isinstance(entry, dict):
            raise CampaignProblem(f"{at} must be a table.")
        number = _whole(entry, "rung", at, low=0)
        if number in seen:
            raise CampaignProblem(f"{at}: rung {number} is declared twice.")
        seen.add(number)

        at = f"{where}: [[ladder]] rung {number}"
        windows = _list_of_text(entry, "windows", at)
        for window in windows:
            if not WINDOW.match(window):
                raise CampaignProblem(
                    f"{at}: window {window!r} is not a window name such as"
                    " test2_5.0-5.5ms, with both times on a 0.1 ms grid."
                )
        # Exclusive of both ends: a bound of 0 declares that nothing is noise
        # and a bound of 1 declares that nothing is a result.
        bound = _number(entry, "noise_bound", at, low=0, high=1)
        if bound <= 0 or bound >= 1:
            raise CampaignProblem(
                f"{at}: noise_bound must be a fraction between 0 and 1"
                f" exclusive, not {bound!r}; 15 per cent is 0.15."
            )
        rungs.append(
            Rung(
                number=number,
                windows=tuple(windows),
                noise_bound=bound,
                repeats=_whole(entry, "repeats", at, low=1),
            )
        )

    rungs.sort(key=lambda r: r.number)

    placed = {}
    for rung in rungs:
        for window in rung.windows:
            if window in placed:
                raise CampaignProblem(
                    f"{where}: window {window!r} is on rung {placed[window]} and"
                    f" rung {rung.number}; a window belongs to one rung."
                )
            placed[window] = rung.number

    return tuple(rungs)


def _approval(data, where):
    """The approval record, or (None, why it cannot be used).

    An incomplete record is not an error at load time. The runner refuses on
    it, and a half-written campaign still has to be readable.
    """

    table = data.get("approval")
    if table is None:
        return None, ""
    if not isinstance(table, dict):
        return None, "[approval] is not a table"

    try:
        approved_on = _text(table, "approved_on", where)
        try:
            datetime.date.fromisoformat(approved_on)
        except ValueError:
            return None, f"[approval] approved_on is {approved_on!r}, not a date"
        return (
            Approval(
                approved_by=_text(table, "approved_by", where),
                approved_on=approved_on,
                slot_hours=_number(table, "slot_hours", where, low=0),
                scope=_text(table, "scope", where, allow_empty=True),
            ),
            "",
        )
    except CampaignProblem as problem:
        # Reported as an incomplete approval rather than a broken file, because
        # that is the distinction the runner acts on.
        detail = str(problem).split(": ", 1)[-1].rstrip(".")
        return None, f"[approval] is incomplete, {detail}"


def load_campaign(path):
    """Read and validate one `campaign.toml`. Raises CampaignProblem."""

    where = os.path.basename(os.path.dirname(os.path.abspath(path))) or path
    where = f"campaign {where}"

    if not os.path.exists(path):
        raise CampaignProblem(f"{where}: no campaign file at {path}.")
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise CampaignProblem(f"{where}: {path} is not valid TOML ({exc}).") from exc

    for name in REQUIRED_TABLES:
        _table(data, name, where)

    meta = data["campaign"]
    build = data["build"]
    limits = data["limits"]
    disk = data["disk"]
    correctness = data["correctness"]
    machine = data["machine"]

    launch = _list_of_text(machine, "launch", f"{where}: [machine]")
    if not any("{case}" in word for word in launch):
        raise CampaignProblem(
            f"{where}: [machine] launch must contain {{case}}, or the launcher is"
            " never told which case to run."
        )
    slots = machine.get("slots")
    if not isinstance(slots, list) or not slots or not all(
        isinstance(s, int) and not isinstance(s, bool) for s in slots
    ):
        raise CampaignProblem(
            f"{where}: [machine] slots must be a non-empty list of whole numbers."
        )

    campaign = Campaign(
        path=path,
        name=_text(meta, "name", f"{where}: [campaign]"),
        goal=_text(meta, "goal", f"{where}: [campaign]"),
        test=_text(meta, "test", f"{where}: [campaign]"),
        parent=_text(meta, "parent", f"{where}: [campaign]"),
        epoch=_text(meta, "epoch", f"{where}: [campaign]"),
        build={
            "hermes_commit": _text(build, "hermes_commit", f"{where}: [build]"),
            "hermes_branch": _text(build, "hermes_branch", f"{where}: [build]"),
            "build_dir": _text(build, "build_dir", f"{where}: [build]"),
            "limiter": _text(build, "limiter", f"{where}: [build]"),
            "conduction_method": _text(
                build, "conduction_method", f"{where}: [build]"
            ),
            "check_level": _whole(build, "check_level", f"{where}: [build]", low=0),
        },
        recipe=_text(data["baseline"], "recipe", f"{where}: [baseline]"),
        search_space=_text(data["search"], "space", f"{where}: [search]"),
        rungs=_rungs(data, where),
        limits={
            # Two to three times the best time for the window (design.md 6).
            "cutoff_factor": _number(
                limits, "cutoff_factor", f"{where}: [limits]", low=1.0
            ),
            "stall_s": _whole(limits, "stall_s", f"{where}: [limits]"),
            # The backstop before any window has a best time to multiply.
            "max_wall_s": _whole(limits, "max_wall_s", f"{where}: [limits]"),
            "poll_s": _whole(limits, "poll_s", f"{where}: [limits]"),
        },
        slot_hours=_number(data["budget"], "slot_hours", f"{where}: [budget]", low=0),
        disk={
            "budget_gb": _number(disk, "budget_gb", f"{where}: [disk]", low=0),
            "floor_gb": _number(disk, "floor_gb", f"{where}: [disk]", low=0),
            "keep_recent": _whole(disk, "keep_recent", f"{where}: [disk]", low=0),
            "keep": _list_of_text(disk, "keep", f"{where}: [disk]", allow_empty=True),
        },
        correctness={
            "window_tolerance": _number(
                correctness, "window_tolerance", f"{where}: [correctness]",
                low=0, high=1,
            ),
            "endpoint_tolerance": _number(
                correctness, "endpoint_tolerance", f"{where}: [correctness]",
                low=0, high=1,
            ),
            "quantities": _list_of_text(
                correctness, "quantities", f"{where}: [correctness]"
            ),
        },
        machine={
            "cores_per_run": _whole(
                machine, "cores_per_run", f"{where}: [machine]"
            ),
            "slots": list(slots),
            "launch": launch,
        },
    )

    if campaign.limits["max_wall_s"] <= campaign.limits["stall_s"]:
        raise CampaignProblem(
            f"{where}: [limits] max_wall_s must exceed stall_s, or every run is"
            " killed by the backstop before the stall check can fire."
        )
    if campaign.disk["floor_gb"] >= campaign.disk["budget_gb"]:
        raise CampaignProblem(
            f"{where}: [disk] floor_gb must be below budget_gb, or the runner"
            " refuses to launch as soon as the campaign uses its budget."
        )

    quantities = campaign.correctness["quantities"]
    from .index import INDEX_COLUMNS

    unknown = [q for q in quantities if q not in INDEX_COLUMNS]
    if unknown:
        raise CampaignProblem(
            f"{where}: [correctness] quantities names no index column:"
            f" {', '.join(unknown)}."
        )

    approval, problem = _approval(data, where)
    return dataclasses.replace(
        campaign, approval=approval, approval_problem=problem
    )
