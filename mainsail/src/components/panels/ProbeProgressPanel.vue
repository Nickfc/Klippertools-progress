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
                    <span class="probe-progress-status">
                        <span class="probe-progress-status__dot" :class="'probe-progress-status__dot--' + visualState" />
                        {{ primaryStatus }}
                    </span>
                    <v-chip v-if="secondaryStatus" x-small outlined class="probe-progress-sample">
                        {{ secondaryStatus }}
                    </v-chip>
                </div>

                <div class="probe-progress-plate">
                    <span class="probe-progress-axis probe-progress-axis--y">Y</span>
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
                    <span class="probe-progress-axis probe-progress-axis--x">X</span>
                </div>

                <div class="probe-progress-legend" aria-hidden="true">
                    <span v-for="state in ['pending', 'active', 'done']" :key="state">
                        <i :class="'probe-progress-legend__swatch--' + state" />
                        {{ $t(`Panels.ProbeProgressPanel.States.${state}`) }}
                    </span>
                </div>

                <v-progress-linear
                    class="probe-progress-bar"
                    :value="progress"
                    :color="progressColor"
                    background-color="grey darken-3"
                    height="26"
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

    get visualState(): string {
        if (this.probeProgress?.state === 'complete') return 'done'
        if (this.probeProgress?.state === 'error') return 'error'
        if (this.probeProgress?.active) return 'active'
        return 'pending'
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
    padding: 14px 16px 16px;
}

.probe-progress-details {
    align-items: center;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
    font-size: 0.82rem;
}

.probe-progress-status {
    align-items: center;
    display: inline-flex;
    font-weight: 600;
    gap: 8px;
}

.probe-progress-status__dot {
    border-radius: 50%;
    display: inline-block;
    height: 9px;
    width: 9px;
}

.probe-progress-status__dot--pending {
    background: #ef5350;
}

.probe-progress-status__dot--active {
    background: #ffca28;
    box-shadow: 0 0 0 4px rgba(255, 202, 40, 0.14);
}

.probe-progress-status__dot--done {
    background: #66bb6a;
}

.probe-progress-status__dot--error {
    background: var(--v-error-base);
}

.probe-progress-sample {
    opacity: 0.82;
}

.probe-progress-plate {
    position: relative;
    width: 100%;
    max-width: 440px;
    margin: 0 auto 10px;
    padding: 16px 16px 20px 22px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    background:
        radial-gradient(circle at 50% 35%, rgba(255, 255, 255, 0.05), transparent 62%),
        rgba(0, 0, 0, 0.2);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        0 6px 18px rgba(0, 0, 0, 0.16);
}

.probe-progress-plate::before,
.probe-progress-plate::after {
    position: absolute;
    border-radius: 50%;
    background: rgba(127, 127, 127, 0.35);
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.45);
    content: '';
    height: 5px;
    top: 7px;
    width: 5px;
}

.probe-progress-plate::before {
    left: 8px;
}

.probe-progress-plate::after {
    right: 8px;
}

.probe-progress-matrix {
    display: grid;
    gap: 6px;
}

.probe-progress-axis {
    position: absolute;
    color: rgba(127, 127, 127, 0.8);
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.08em;
}

.probe-progress-axis--y {
    left: 8px;
    top: 50%;
    transform: translateY(-50%) rotate(-90deg);
}

.probe-progress-axis--x {
    bottom: 5px;
    left: 50%;
    transform: translateX(-50%);
}

.probe-progress-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    aspect-ratio: 1;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 5px;
    color: rgba(255, 255, 255, 0.86);
    font-size: clamp(0.56rem, 1vw, 0.74rem);
    font-weight: 600;
    transition:
        background-color 180ms ease,
        box-shadow 180ms ease,
        transform 180ms ease;
}

.probe-progress-cell--pending {
    background: linear-gradient(145deg, #d43b32, #9f211b);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.probe-progress-cell--active {
    z-index: 1;
    color: #201600;
    background: linear-gradient(145deg, #ffd54f, #f39c12);
    box-shadow:
        0 0 0 2px rgba(255, 213, 79, 0.35),
        0 0 16px rgba(249, 168, 37, 0.5);
    transform: scale(1.04);
    animation: probe-progress-pulse 1.25s ease-in-out infinite;
}

.probe-progress-cell--done {
    background: linear-gradient(145deg, #43a047, #24762a);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.probe-progress-cell--empty {
    visibility: hidden;
}

.probe-progress-legend {
    align-items: center;
    display: flex;
    justify-content: center;
    gap: 14px;
    margin: 0 0 12px;
    color: rgba(127, 127, 127, 0.95);
    font-size: 0.68rem;
}

.probe-progress-legend span {
    align-items: center;
    display: inline-flex;
    gap: 5px;
}

.probe-progress-legend i {
    border-radius: 3px;
    display: inline-block;
    height: 8px;
    width: 8px;
}

.probe-progress-legend__swatch--pending {
    background: #c4352c;
}

.probe-progress-legend__swatch--active {
    background: #ffca28;
}

.probe-progress-legend__swatch--done {
    background: #43a047;
}

.probe-progress-bar {
    color: white;
    font-size: 0.74rem;
    letter-spacing: 0.01em;
    box-shadow: inset 0 0 0 1px rgba(127, 127, 127, 0.22);
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
