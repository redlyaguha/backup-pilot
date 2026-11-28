"""Plan retention conservatively; apply re-plans under the profile lock."""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from .backup import list_snapshots
from .errors import BackupPilotError
from .integrity import read_manifest
from .locking import profile_lock
from .profiles import check_plain_path

@dataclass(frozen=True)
class RetentionPlan:
    keep: tuple[Path, ...]
    remove: tuple[Path, ...]

def plan_retention(profile):
    eligible = []
    for snapshot in list_snapshots(profile):
        try:
            read_manifest(profile, snapshot.name)
        except BackupPilotError as error:
            if error.code == 3:
                raise
            continue
        eligible.append(snapshot)
    eligible.sort(key=lambda p: p.name)
    count = max(1, profile.keep_last)
    return RetentionPlan(tuple(eligible[-count:]), tuple(eligible[:-count]))

def apply_retention(profile):
    if not shutil.rmtree.avoids_symlink_attacks:
        raise BackupPilotError('Безопасное удаление требует Linux с поддержкой dir_fd.', 4)
    with profile_lock(profile):
        plan = plan_retention(profile)
        root = profile.destination / profile.name
        if not plan.remove:
            return plan
        check_plain_path(root)
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for snapshot in plan.remove:
                read_manifest(profile, snapshot.name)
                shutil.rmtree(snapshot.name, dir_fd=fd)
        finally:
            os.close(fd)
        return plan
