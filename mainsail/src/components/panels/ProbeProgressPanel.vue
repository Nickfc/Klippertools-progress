<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && probeProgress"
        :icon="mdiGrid"
        :title="$t('Panels.ProbeProgressPanel.Headline')"
        :collapsible="true"
        card-class="probe-progress-panel"
        :hide-buttons-on-collapse="true">
        <template #buttons-title>
            <div v-if="hasMatrix" class="probe-progress-header ml-2">
                <span>{{ columns }} × {{ rows }}</span>
                <span v-if="isActive">· {{ currentPointLabel }}</span>
            </div>
        </template>

        <v-card-text class="probe-progress-content">
            <template v-if="hasMatrix">
                <div class="probe-progress-details">
                    <span>{{ primaryStatus }}</span>
                    <span v-if="secondaryStatus">{{ secondaryStatus }}</span>
                </div>

                <div
                    class="probe-progress-matrix"
                    role="grid"
                    :aria-label="$t('Panels.ProbeProgressPanel.MatrixLabel')"
                    :style="matrixStyle">
                    <template v-for="(cell, slotIndex) in matrixSlots">
                        <div
                            v-if="cell"
                            :key="'cell-' + cell.index"
                            class="probe-progress-cell"
                            :class="'probe-progress-cell--' + cell.state"
                            role="gridcell"
                            :title="cellTitle(cell)"
                            :aria-label="cellTitle(cell)">
                            <span>{{ cell.index }}</span>
                        </div>
                        <div
                            v-else
                            :key="'empty-' + slotIndex"
                            class="probe-progress-cell probe-progress-cell--empty"
                            aria-hidden="true" />
                    </template>
                </div>

                <v-progress-linear
                    class="probe-progress-bar"
                    :value="progress"
                    :color="progressColor"
                    background-color="#8c2020"
                    height="24"
                    rounded>
                    <strong>{{ progressBarText }}</strong>
                </v-progress-linear>

                <div v-if="probeProgress.error" class="probe-progress-error mt-2">
                    {{ probeProgress.error }}
                </div>
            </template>

            <div v-else class="probe-progress-empty">
                <v-icon large class="mb-2">{{ mdiGrid }}</v-icon>
                <div>{{ $t('Panels.ProbeProgressPanel.Ready') }}</div>
                <small>{{ $t('Panels.ProbeProgressPanel.Empty') }}</small>
            </div>
        </v-card-text>
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import Panel from '@/components/ui/Panel.vue'
import { mdiGrid } from '@mdi/js'

interface ProbeProgressCell {
    index: number
    row: number
    column: number
    x: number
    y: number
    state: 'pending' | 'active' | 'done'
}

interface ProbeProgressStatus {
    state: 'idle' | 'probing' | 'complete' | 'error'
    phase: string
    active: boolean
    message: string
    error: string | null
    current_point: number
    completed_points: number
    total_points: number
    current_sample: number
    samples_per_position: number
    current_retry: number
    samples_retries: number
    progress: number
    eta_state: 'calculating' | 'available'
    eta_seed_points: number
    eta_sampled_points: number
    eta_seconds: number | null
    elapsed_seconds: number
    matrix: {
        rows: number
        columns: number
        cells: ProbeProgressCell[]
    }
}

@Component({
    components: {
        Panel,
    },
})
export default class ProbeProgressPanel extends Mixins(BaseMixin) {
    mdiGrid = mdiGrid

    get probeProgress(): ProbeProgressStatus | null {
        return this.$store.state.printer?.probe_progress ?? null
    }

    get hasMatrix(): boolean {
        return (this.probeProgress?.matrix?.cells?.length ?? 0) > 0
    }

    get isActive(): boolean {
        return this.probeProgress?.active ?? false
    }

    get rows(): number {
        return this.probeProgress?.matrix?.rows ?? 0
    }

    get columns(): number {
        return this.probeProgress?.matrix?.columns ?? 0
    }

    get progress(): number {
        return this.probeProgress?.progress ?? 0
    }

    get matrixStyle() {
        return {
            gridTemplateColumns: `repeat(${this.columns}, minmax(0, 1fr))`,
        }
    }

    get matrixSlots(): Array<ProbeProgressCell | null> {
        const slots: Array<ProbeProgressCell | null> = Array(this.rows * this.columns).fill(null)
        for (const cell of this.probeProgress?.matrix?.cells ?? []) {
            const index = cell.row * this.columns + cell.column
            if (index >= 0 && index < slots.length) slots[index] = cell
        }
        return slots
    }

    get currentPointLabel(): string {
        return String(
            this.$t('Panels.ProbeProgressPanel.PointOf', {
                current: this.probeProgress?.current_point ?? 0,
                total: this.probeProgress?.total_points ?? 0,
            })
        )
    }

    get primaryStatus(): string {
        const status = this.probeProgress
        if (!status) return ''
        if (status.state === 'complete')
            return String(this.$t('Panels.ProbeProgressPanel.Complete'))
        if (status.state === 'error')
            return String(this.$t('Panels.ProbeProgressPanel.Stopped'))
        if (status.phase === 'zero_reference')
            return String(this.$t('Panels.ProbeProgressPanel.ZeroReference'))
        return this.currentPointLabel
    }

    get secondaryStatus(): string {
        const status = this.probeProgress
        if (!status || !status.active || status.current_point < 1) return ''
        if (status.current_retry > 0) {
            return String(
                this.$t('Panels.ProbeProgressPanel.RetryOf', {
                    current: status.current_retry,
                    total: status.samples_retries,
                })
            )
        }
        return String(
            this.$t('Panels.ProbeProgressPanel.SampleOf', {
                current: status.current_sample,
                total: status.samples_per_position,
            })
        )
    }

    get progressColor(): string {
        if (this.probeProgress?.state === 'error') return 'error'
        if (this.probeProgress?.state === 'complete') return '#2e7d32'
        return '#43a047'
    }

    get progressBarText(): string {
        const status = this.probeProgress
        if (!status) return ''
        const percent = `${Math.round(status.progress)}%`

        if (status.state === 'complete') {
            return `${percent} · ${String(
                this.$t('Panels.ProbeProgressPanel.CompleteIn', {
                    time: this.formatDuration(status.elapsed_seconds),
                })
            )}`
        }
        if (status.state === 'error')
            return `${percent} · ${String(this.$t('Panels.ProbeProgressPanel.Stopped'))}`
        if (status.eta_state === 'available' && status.eta_seconds !== null) {
            return `${percent} · ${String(
                this.$t('Panels.ProbeProgressPanel.Remaining', {
                    time: this.formatDuration(status.eta_seconds),
                })
            )}`
        }
        return `${percent} · ${String(
            this.$t('Panels.ProbeProgressPanel.Calculating', {
                current: status.eta_sampled_points,
                total: status.eta_seed_points,
            })
        )}`
    }

    formatDuration(totalSeconds: number): string {
        const seconds = Math.max(0, Math.round(totalSeconds))
        const hours = Math.floor(seconds / 3600)
        const minutes = Math.floor((seconds % 3600) / 60)
        const remainder = seconds % 60
        if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`
        if (minutes > 0) return `${minutes}m ${String(remainder).padStart(2, '0')}s`
        return `${remainder}s`
    }

    cellTitle(cell: ProbeProgressCell): string {
        return String(
            this.$t('Panels.ProbeProgressPanel.CellLabel', {
                point: cell.index,
                x: cell.x,
                y: cell.y,
                state: this.$t(`Panels.ProbeProgressPanel.States.${cell.state}`),
            })
        )
    }
}
</script>

<style scoped>
.probe-progress-header {
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}

.probe-progress-content {
    padding: 16px;
}

.probe-progress-details {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.82rem;
}

.probe-progress-matrix {
    display: grid;
    gap: 6px;
    width: 100%;
    max-width: 440px;
    margin: 0 auto 14px;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    background: #151515;
}

.probe-progress-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    aspect-ratio: 1;
    border-radius: 4px;
    color: rgba(255, 255, 255, 0.86);
    font-size: clamp(0.56rem, 1vw, 0.74rem);
    font-weight: 600;
    transition:
        background-color 180ms ease,
        box-shadow 180ms ease,
        transform 180ms ease;
}

.probe-progress-cell--pending {
    background: #b3261e;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.probe-progress-cell--active {
    z-index: 1;
    color: #201600;
    background: #f9a825;
    box-shadow:
        0 0 0 2px rgba(255, 213, 79, 0.35),
        0 0 16px rgba(249, 168, 37, 0.5);
    transform: scale(1.04);
    animation: probe-progress-pulse 1.25s ease-in-out infinite;
}

.probe-progress-cell--done {
    background: #2e7d32;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.probe-progress-cell--empty {
    visibility: hidden;
}

.probe-progress-bar {
    color: white;
    font-size: 0.76rem;
    letter-spacing: 0.01em;
}

.probe-progress-error {
    color: var(--v-error-base);
    font-size: 0.8rem;
}

.probe-progress-empty {
    display: flex;
    min-height: 150px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.62);
    text-align: center;
}

.probe-progress-empty small {
    max-width: 320px;
    margin-top: 4px;
    color: rgba(255, 255, 255, 0.45);
}

@keyframes probe-progress-pulse {
    0%,
    100% {
        box-shadow:
            0 0 0 2px rgba(255, 213, 79, 0.28),
            0 0 10px rgba(249, 168, 37, 0.36);
    }
    50% {
        box-shadow:
            0 0 0 3px rgba(255, 213, 79, 0.45),
            0 0 20px rgba(249, 168, 37, 0.64);
    }
}

@media (max-width: 600px) {
    .probe-progress-matrix {
        gap: 4px;
        padding: 8px;
    }
}
</style>
