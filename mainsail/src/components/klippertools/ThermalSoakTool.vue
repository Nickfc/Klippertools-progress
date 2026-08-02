<template>
    <div class="thermal-soak pa-4">
        <v-alert v-if="!status || !status.ready" dense text type="info" class="mb-3">
            Thermal Soak is unavailable until Klipper loads the optional module.
        </v-alert>

        <template v-else>
            <div class="d-flex align-start justify-space-between mb-3">
                <div>
                    <div class="text-caption text--secondary">{{ sensorLabel }}</div>
                    <div class="thermal-soak__temperature">
                        {{ temperatureText }}
                        <span v-if="status.target">/ {{ status.target.toFixed(1) }} °C</span>
                    </div>
                </div>
                <v-chip small outlined :color="stateColor">{{ stateLabel }}</v-chip>
            </div>

            <v-progress-linear :value="status.progress" :color="stateColor" height="9" rounded class="mb-3" />

            <v-row dense class="mb-2">
                <v-col cols="4">
                    <div class="thermal-soak__metric">
                        <span>Slope</span>
                        <strong>{{ slopeText }}</strong>
                    </div>
                </v-col>
                <v-col cols="4">
                    <div class="thermal-soak__metric">
                        <span>Range</span>
                        <strong>{{ rangeText }}</strong>
                    </div>
                </v-col>
                <v-col cols="4">
                    <div class="thermal-soak__metric">
                        <span>Remaining</span>
                        <strong>{{ etaText }}</strong>
                    </div>
                </v-col>
            </v-row>

            <v-alert v-if="status.error" dense text type="error" class="mb-3">
                {{ status.error }}
            </v-alert>
            <div v-else class="text-caption text--secondary mb-3">
                {{ status.message }}. Monitoring never changes a heater target.
            </div>

            <v-expansion-panels v-if="!status.active" flat accordion class="mb-2">
                <v-expansion-panel>
                    <v-expansion-panel-header class="px-0 py-1">Soak settings</v-expansion-panel-header>
                    <v-expansion-panel-content class="px-0">
                        <v-select
                            v-model="sensor"
                            :items="status.available_sensors"
                            label="Temperature sensor"
                            dense
                            outlined
                            hide-details
                            class="mb-3" />
                        <v-row dense>
                            <v-col cols="6">
                                <v-text-field
                                    v-model.number="target"
                                    type="number"
                                    label="Target"
                                    suffix="°C"
                                    min="1"
                                    max="500"
                                    step="1"
                                    dense
                                    outlined />
                            </v-col>
                            <v-col cols="6">
                                <v-text-field
                                    v-model.number="windowMinutes"
                                    type="number"
                                    label="Stable window"
                                    suffix="min"
                                    min="0.5"
                                    max="60"
                                    step="0.5"
                                    dense
                                    outlined />
                            </v-col>
                            <v-col cols="6">
                                <v-text-field
                                    v-model.number="tolerance"
                                    type="number"
                                    label="Target tolerance"
                                    suffix="°C"
                                    min="0.05"
                                    max="10"
                                    step="0.05"
                                    dense
                                    outlined />
                            </v-col>
                            <v-col cols="6">
                                <v-text-field
                                    v-model.number="maxWaitMinutes"
                                    type="number"
                                    label="Maximum wait"
                                    suffix="min"
                                    min="1"
                                    max="240"
                                    step="1"
                                    dense
                                    outlined />
                            </v-col>
                        </v-row>
                    </v-expansion-panel-content>
                </v-expansion-panel>
            </v-expansion-panels>

            <div class="d-flex justify-space-between">
                <v-btn small text :disabled="status.active" @click="reset">
                    <v-icon small left>{{ mdiRefresh }}</v-icon>
                    Reset
                </v-btn>
                <v-btn v-if="status.active" small text color="error" @click="cancel">
                    <v-icon small left>{{ mdiStopCircleOutline }}</v-icon>
                    Cancel
                </v-btn>
                <v-btn v-else small color="primary" :disabled="!canStart" @click="start">
                    <v-icon small left>{{ mdiThermometerChevronUp }}</v-icon>
                    Start monitoring
                </v-btn>
            </div>
        </template>
    </div>
</template>

<script lang="ts">
import { Component, Mixins, Watch } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { mdiRefresh, mdiStopCircleOutline, mdiThermometerChevronUp } from '@mdi/js'
import { ThermalSoakStatus } from '@/components/klippertools/types'

@Component
export default class ThermalSoakTool extends Mixins(BaseMixin) {
    mdiRefresh = mdiRefresh
    mdiStopCircleOutline = mdiStopCircleOutline
    mdiThermometerChevronUp = mdiThermometerChevronUp

    sensor = 'heater_bed'
    target = 60
    windowMinutes = 5
    maxWaitMinutes = 30
    tolerance = 0.3
    initializedSession = -1

    get status(): ThermalSoakStatus | null {
        return this.$store.state.printer?.thermal_soak ?? null
    }

    @Watch('status.session_id', { immediate: true })
    initializeDefaults(): void {
        if (!this.status || this.initializedSession >= 0) return
        const defaults = this.status.defaults
        const configuredSensor = defaults?.sensor
        this.sensor =
            (configuredSensor && this.status.available_sensors.includes(configuredSensor)
                ? configuredSensor
                : this.status.available_sensors[0]) || 'heater_bed'
        this.windowMinutes = (defaults?.window_seconds || 300) / 60
        this.maxWaitMinutes = (defaults?.max_wait_seconds || 1800) / 60
        this.tolerance = defaults?.temperature_tolerance || 0.3
        this.initializedSession = this.status.session_id
    }

    get canStart(): boolean {
        return Boolean(
            this.sensor &&
            Number(this.target) > 0 &&
            Number(this.windowMinutes) >= 0.5 &&
            Number(this.maxWaitMinutes) >= 1 &&
            Number(this.tolerance) > 0
        )
    }

    get sensorLabel(): string {
        return this.status?.sensor || this.sensor || 'Temperature sensor'
    }

    get temperatureText(): string {
        return this.status?.temperature == null ? '—' : `${this.status.temperature.toFixed(1)} °C`
    }

    get slopeText(): string {
        return this.status?.slope_c_per_min == null ? '—' : `${this.status.slope_c_per_min.toFixed(3)} °C/min`
    }

    get rangeText(): string {
        return this.status?.range_c == null ? '—' : `${this.status.range_c.toFixed(2)} °C`
    }

    get etaText(): string {
        const value = this.status?.eta_seconds
        if (value == null) return 'Calculating'
        if (value <= 0) return 'Ready'
        const minutes = Math.floor(value / 60)
        const seconds = value % 60
        return minutes ? `${minutes}m ${seconds}s` : `${seconds}s`
    }

    get stateLabel(): string {
        const labels: Record<string, string> = {
            idle: 'Idle',
            heating: 'Heating',
            stabilizing: 'Stabilizing',
            stable: 'Stable',
            timed_out: 'Timed out',
            canceled: 'Canceled',
            error: 'Error',
        }
        return labels[this.status?.state || 'idle'] || this.status?.state || 'Idle'
    }

    get stateColor(): string {
        const state = this.status?.state
        if (state === 'stable') return 'success'
        if (['timed_out', 'error'].includes(state || '')) return 'error'
        if (state === 'stabilizing') return 'warning'
        return 'primary'
    }

    start(): void {
        if (!this.canStart) return
        const safeSensor = this.sensor.replace(/["\\\r\n]/g, '')
        const script = [
            'THERMAL_SOAK_START',
            `SENSOR="${safeSensor}"`,
            `TARGET=${Number(this.target).toFixed(2)}`,
            `WINDOW=${Math.round(Number(this.windowMinutes) * 60)}`,
            `MAX_WAIT=${Math.round(Number(this.maxWaitMinutes) * 60)}`,
            `TOLERANCE=${Number(this.tolerance).toFixed(3)}`,
        ].join(' ')
        this.$socket.emit('printer.gcode.script', { script }, { loading: 'thermalSoakStart' })
    }

    cancel(): void {
        this.$socket.emit('printer.gcode.script', { script: 'THERMAL_SOAK_CANCEL' }, { loading: 'thermalSoakCancel' })
    }

    reset(): void {
        this.$socket.emit('printer.gcode.script', { script: 'THERMAL_SOAK_RESET' }, { loading: 'thermalSoakReset' })
    }
}
</script>

<style scoped>
.thermal-soak__temperature {
    font-size: 1.55rem;
    font-weight: 600;
    line-height: 1.3;
}

.thermal-soak__temperature span {
    color: rgba(127, 127, 127, 0.88);
    font-size: 0.9rem;
    font-weight: 400;
}

.thermal-soak__metric {
    background: rgba(127, 127, 127, 0.055);
    border: 1px solid rgba(127, 127, 127, 0.13);
    border-radius: 8px;
    min-height: 62px;
    padding: 8px;
}

.thermal-soak__metric span,
.thermal-soak__metric strong {
    display: block;
}

.thermal-soak__metric span {
    color: rgba(127, 127, 127, 0.9);
    font-size: 0.72rem;
}

.thermal-soak__metric strong {
    font-size: 0.78rem;
    margin-top: 4px;
}
</style>
