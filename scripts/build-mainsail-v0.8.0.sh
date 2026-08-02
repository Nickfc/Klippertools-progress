#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-$ROOT/build/mainsail-v0.8.0}"
WORK="${KLIPPERTOOLS_BUILD_WORK:-$ROOT/build/.mainsail-v0.8.0-work}"
VERSIONS=(v2.17.0 v2.18.2)
CHANGED_FILES=(
    src/components/klippertools/CalibrationCenterTool.vue
    src/components/klippertools/HealthTimelineTool.vue
    src/components/klippertools/MaintenanceTrackerTool.vue
    src/components/klippertools/MotionWizardTool.vue
    src/components/klippertools/NozzleGuardTool.vue
    src/components/klippertools/StartFlowTool.vue
    src/components/klippertools/ThermalSoakTool.vue
    src/components/klippertools/ToolRegistryTool.vue
    src/components/klippertools/types.ts
    src/components/mixins/dashboard.ts
    src/components/panels/CalibrationCenterPanel.vue
    src/components/panels/HealthTimelinePanel.vue
    src/components/panels/KlippertoolsPanel.vue
    src/components/panels/MaintenanceTrackerPanel.vue
    src/components/panels/MotionWizardPanel.vue
    src/components/panels/NozzleGuardPanel.vue
    src/components/panels/ProbeProgressPanel.vue
    src/components/panels/StartFlowPanel.vue
    src/components/panels/ThermalSoakPanel.vue
    src/components/panels/ToolRegistryPanel.vue
    src/pages/Dashboard.vue
    src/pages/Klippertools.vue
    src/routes/index.ts
    src/store/gui/getters.ts
    src/store/gui/index.ts
    src/store/variables.ts
)

rm -rf -- "$OUTPUT" "$WORK"
mkdir -p "$OUTPUT" "$WORK"

for version in "${VERSIONS[@]}"; do
    source_zip="$ROOT/source/mainsail-${version}-klippertools-source.zip"
    source_dir="$WORK/$version"

    [[ -f "$source_zip" ]] || { echo "missing $source_zip" >&2; exit 1; }
    mkdir -p "$source_dir"
    unzip -q "$source_zip" -d "$source_dir"
    rm -rf -- "$source_dir/.git" "$source_dir/node_modules" "$source_dir/dist"

    (
        cd "$source_dir"
        npm ci --no-audit --no-fund
        npx eslint "${CHANGED_FILES[@]}"
        rm -rf -- dist
        npm run build

        # Mainsail creates dist/mainsail.zip. Klippertools UI archives contain
        # compiled files directly and must never nest that generated ZIP.
        rm -f -- dist/mainsail.zip
        printf '%s' "$version" > dist/.version
        printf 'Klippertools Suite UI 0.8.0\n' > dist/klippertools-build.txt
        ! find dist -type f -name mainsail.zip -print -quit | grep -q .
        (cd dist && zip -qr "$OUTPUT/mainsail-${version}-klippertools.zip" .)
    )
done

(
    cd "$OUTPUT"
    sha256sum \
        mainsail-v2.17.0-klippertools.zip \
        mainsail-v2.18.2-klippertools.zip \
        > SHA256SUMS.mainsail-v0.8.0
)

for archive in "$OUTPUT"/*.zip; do
    unzip -tq "$archive" >/dev/null
done

for version in "${VERSIONS[@]}"; do
    archive="$OUTPUT/mainsail-${version}-klippertools.zip"
    [[ "$(unzip -p "$archive" .version)" == "$version" ]]
    [[ "$(unzip -p "$archive" klippertools-build.txt | head -n1)" == 'Klippertools Suite UI 0.8.0' ]]
    if unzip -Z1 "$archive" | grep -Eq '(^|/)mainsail\.zip$'; then
        echo "nested mainsail.zip found in $archive" >&2
        exit 1
    fi
done

printf 'Mainsail v0.8.0 builds completed in %s\n' "$OUTPUT"
