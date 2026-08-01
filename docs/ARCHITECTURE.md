# Architecture

## Data flow

1. The Klipper extra loads as the object probe_progress.
2. After Klipper is ready, it observes Bed Mesh's ProbeManager start call.
3. Bed Mesh has already generated the command's real base points, physical
   probe path, counts, bounds, and faulty-region substitutions.
4. The extra records every physical touch from probe:update_results.
5. A logical cell becomes complete only after Klipper's configured sample
   count passes tolerance for every physical substitute belonging to it.
6. Klipper exposes the resulting status through its normal object-status API.
7. Mainsail already subscribes to Klipper objects, so no custom Moonraker
   component or polling endpoint is required.

## Matrix model

Cells are laid out with increasing X from left to right and decreasing Y from
top to bottom, which gives the dashboard a physical top-down bed orientation.
Klipper's serpentine execution order changes cell numbers and activation order
without changing that physical layout.

The public state for each cell is pending, active, or done. Probe samples and
tolerance retry sets are internal to the active cell. A faulty logical point
can expand into several physical positions; it turns green only after all of
those positions complete.

## ETA model

The timer for a logical point begins when it becomes active and ends when it
turns green. This includes travel from the preceding point, all configured
samples, sample retracts, and any tolerance retries incurred during the seed
point.

After the first three logical points complete, the backend calculates:

    seconds_per_point = duration(first three points) / 3
    deadline = current_time + seconds_per_point * remaining_points

The deadline is intentionally fixed after those first three points, matching
the requested behavior. The displayed remaining time counts down from it.
Meshes with fewer than three logical points use every available point.

## Integration boundary

The backend hooks a Klipper Bed Mesh internal method because Klipper does not
currently expose a dedicated public bed-mesh progress event. The exact
integration has been checked against the two listed Klipper revisions. The
Mainsail side is also a native patch because Mainsail v2 has no external
dashboard-card API.

The installer makes both integration boundaries explicit: it uses a
version-matched Mainsail build and retains a full rollback copy.
