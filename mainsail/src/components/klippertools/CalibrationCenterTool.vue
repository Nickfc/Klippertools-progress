<template>
    <div class="calibration-center pa-4">
        <v-alert v-if="!status || !status.ready" dense text type="info" class="mb-3">
            Calibration Center is unavailable until Klipper loads the optional module.
        </v-alert>

        <template v-else>
            <div class="d-flex flex-wrap align-start justify-space-between mb-3">
                <div>
                    <div class="text-subtitle-1 font-weight-medium">Attended calibration workspace</div>
                    <div class="text-caption text--secondary">
                        Klipper's own calibration commands, with prerequisites and review kept visible.
                    </div>
                </div>
                <v-chip small outlined :color="stateColor" class="mt-1">{{ stateLabel }}</v-chip>
            </div>

            <v-alert dense text type="warning" class="mb-4">
                Heat and motion workflows require you to stay beside the printer. Calibration Center never runs
                <strong>SAVE_CONFIG</strong>, restarts Klipper, or invents printer-specific values.
            </v-alert>

            <v-row dense class="mb-2">
                <v-col v-for="flow in flowCards" :key="flow.key" cols="12" sm="6" lg="4">
                    <button
                        type="button"
                        class="calibration-flow"
                        :class="{
                            'calibration-flow--selected': selectedFlow === flow.key,
                            'calibration-flow--disabled': !flow.available,
                        }"
                        :disabled="!flow.available || status.active"
                        @click="selectedFlow = flow.key">
                        <div class="d-flex align-start">
                            <v-icon small class="mr-2 mt-1" :color="flow.available ? 'primary' : undefined">
                                {{ flow.icon }}
                            </v-icon>
                            <div class="text-left flex-grow-1">
                                <div class="font-weight-medium">{{ flow.title }}</div>
                                <div class="text-caption text--secondary">{{ flow.summary }}</div>
                            </div>
                        </div>
                        <div class="d-flex flex-wrap mt-2">
                            <v-chip v-if="flow.heats" x-small outlined color="warning" class="mr-1">Heat</v-chip>
                            <v-chip v-if="flow.moves" x-small outlined color="warning" class="mr-1">Motion</v-chip>
                            <v-chip v-if="flow.permanent_result" x-small outlined class="mr-1">Review result</v-chip>
                            <v-chip v-if="!flow.available" x-small outlined color="error">Unavailable</v-chip>
                        </div>
                        <div v-if="!flow.available && flow.reason" class="text-caption error--text mt-2">
                            {{ flow.reason }}
                        </div>
                    </button>
                </v-col>
            </v-row>

            <v-card outlined class="mb-3">
                <v-card-title class="text-subtitle-1 pb-2">{{ selectedTitle }}</v-card-title>
                <v-card-text>
                    <v-alert v-if="requiresHoming && !allHomed" dense text type="info" class="mb-3">
                        Home X, Y, and Z before starting this workflow.
                    </v-alert>

                    <template v-if="selectedFlow === 'pid'">
                        <v-row dense>
                            <v-col cols="12" md="7">
                                <v-select
                                    v-model="pidHeater"
                                    :items="heaterChoices"
                                    item-text="label"
                                    item-value="value"
                                    label="Configured heater"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                            <v-col cols="12" md="5">
                                <v-text-field
                                    v-model.number="pidTarget"
                                    type="number"
                                    label="Calibration target"
                                    suffix="°C"
                                    :min="selectedHeater ? selectedHeater.min_temp : undefined"
                                    :max="selectedHeater ? selectedHeater.max_temp : undefined"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                        </v-row>
                        <div class="text-caption text--secondary mt-2">
                            {{ heaterLimitText }} No temperature is selected automatically.
                        </div>
                    </template>

                    <template v-else-if="selectedFlow === 'bed_mesh'">
                        <v-text-field
                            v-model="meshProfile"
                            label="Optional profile name"
                            hint="Letters, numbers, dot, dash, and underscore only. Leave blank to use Klipper's default."
                            persistent-hint
                            outlined
                            dense />
                        <div class="text-caption text--secondary">
                            Current active profile: <strong>{{ currentValues.bed_mesh_profile || 'none' }}</strong>. Klipper's
                            configured mesh bounds, probe speed, samples, and faulty regions are used unchanged.
                        </div>
                    </template>

                    <template v-else-if="selectedFlow === 'z_offset'">
                        <v-alert dense text type="info" class="mb-2">
                            Calibration Center starts Klipper's probe or Z-endstop helper. Use the buttons below while the
                            helper is active, then accept or abort. Saving remains a separate manual decision.
                        </v-alert>
                        <v-row dense>
                            <v-col cols="6">
                                <div class="value-card">
                                    <span>Probe Z offset</span>
                                    <strong>{{ numberOrDash(currentValues.probe_z_offset, 4) }}</strong>
                                </div>
                            </v-col>
                            <v-col cols="6">
                                <div class="value-card">
                                    <span>Z endstop position</span>
                                    <strong>{{ numberOrDash(currentValues.z_endstop_position, 4) }}</strong>
                                </div>
                            </v-col>
                        </v-row>
                        <div v-if="manualProbeActive" class="d-flex flex-wrap justify-center mt-3">
                            <v-btn small outlined class="ma-1" @click="manualStep('-')">Move closer</v-btn>
                            <v-btn small outlined class="ma-1" @click="manualStep('+')">Move farther</v-btn>
                            <v-btn small color="success" outlined class="ma-1" @click="manualAccept">Accept</v-btn>
                            <v-btn small color="error" outlined class="ma-1" @click="manualAbort">Abort helper</v-btn>
                        </div>
                    </template>

                    <template v-else-if="selectedFlow === 'input_shaper'">
                        <v-select
                            v-model="shaperAxis"
                            :items="axisChoices"
                            label="Axis"
                            outlined
                            dense
                            hide-details="auto" />
                        <v-row dense class="mt-2">
                            <v-col cols="6">
                                <div class="value-card">
                                    <span>Current X</span>
                                    <strong>{{ shaperText('x') }}</strong>
                                </div>
                            </v-col>
                            <v-col cols="6">
                                <div class="value-card">
                                    <span>Current Y</span>
                                    <strong>{{ shaperText('y') }}</strong>
                                </div>
                            </v-col>
                        </v-row>
                    </template>

                    <template v-else-if="selectedFlow === 'pressure_advance'">
                        <v-alert dense text type="info" class="mb-3">
                            Enter values from the calibration method and test model you chose. This workflow only prepares
                            an exact TUNING_TOWER command for review; it does not arm the tower or start a print.
                        </v-alert>
                        <v-row dense>
                            <v-col cols="12" sm="6">
                                <v-text-field
                                    v-model.number="paStart"
                                    type="number"
                                    label="START"
                                    min="0"
                                    max="5"
                                    step="0.001"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                            <v-col cols="12" sm="6">
                                <v-text-field
                                    v-model.number="paFactor"
                                    type="number"
                                    label="FACTOR"
                                    min="0.000001"
                                    max="1"
                                    step="0.0001"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                        </v-row>
                        <div class="text-caption text--secondary mt-2">
                            Current pressure advance: <strong>{{ numberOrDash(currentValues.pressure_advance, 5) }}</strong>
                        </div>
                        <v-card v-if="pressurePreview" outlined class="command-preview mt-3 pa-3">
                            <div class="text-caption text--secondary mb-1">Reviewed command preview</div>
                            <code>{{ pressurePreview }}</code>
                            <div class="text-caption text--secondary mt-2">
                                Arm this only immediately before the separately reviewed test print. No print starts automatically.
                            </div>
                            <v-btn
                                small
                                outlined
                                color="warning"
                                class="mt-3"
                                :disabled="printerBusy"
                                @click="showPressureSendConfirm = true">
                                <v-icon small left>{{ mdiPlayCircleOutline }}</v-icon>
                                Arm reviewed command
                            </v-btn>
                        </v-card>
                    </template>

                    <template v-else-if="selectedFlow === 'rotation_distance'">
                        <v-alert dense text type="info" class="mb-3">
                            Measurement and extrusion stay outside Calibration Center. This only calculates
                            previous × actual ÷ requested and shows the result for review.
                        </v-alert>
                        <v-row dense>
                            <v-col cols="12" sm="4">
                                <v-text-field
                                    v-model.number="rotationPrevious"
                                    type="number"
                                    label="Previous rotation distance"
                                    min="0.000001"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-text-field
                                    v-model.number="rotationRequested"
                                    type="number"
                                    label="Requested filament"
                                    suffix="mm"
                                    min="0.000001"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-text-field
                                    v-model.number="rotationActual"
                                    type="number"
                                    label="Actual filament moved"
                                    suffix="mm"
                                    min="0.000001"
                                    outlined
                                    dense
                                    hide-details="auto" />
                            </v-col>
                        </v-row>
                    </template>

                    <template v-else-if="selectedFlow === 'first_layer'">
                        <v-alert dense text type="info" class="mb-0">
                            Review nozzle, material, temperatures, bed cleanliness, Z offset, and sliced line width. Start
                            your own first-layer G-code from Mainsail only after those values are correct. This workflow
                            starts no heat, motion, or file.
                        </v-alert>
                    </template>
                </v-card-text>
                <v-card-actions>
                    <v-btn small text :disabled="status.active" @click="reset">
                        <v-icon small left>{{ mdiRefresh }}</v-icon>
                        Reset session
                    </v-btn>
                    <v-btn v-if="status.active" small text color="error" @click="abort">
                        <v-icon small left>{{ mdiStopCircleOutline }}</v-icon>
                        Abort workflow
                    </v-btn>
                    <v-spacer />
                    <v-btn small color="primary" :disabled="!canPrepare" @click="showConfirm = true">
                        <v-icon small left>{{ mdiPlayCircleOutline }}</v-icon>
                        {{ actionLabel }}
                    </v-btn>
                </v-card-actions>
            </v-card>

            <v-alert v-if="status.error" dense text type="error" class="mb-3">{{ status.error }}</v-alert>
            <v-alert v-else-if="status.message" dense text :type="messageType" class="mb-3">
                {{ status.message }}
            </v-alert>

            <v-card v-if="status.last_result" outlined class="pa-3 result-card">
                <div class="text-caption text--secondary mb-2">Latest review result</div>
                <div v-for="(value, key) in resultRows" :key="key" class="result-row">
                    <span>{{ humanize(key) }}</span>
                    <strong>{{ value }}</strong>
                </div>
                <v-alert v-if="status.current_values.save_config_pending" dense text type="warning" class="mt-3 mb-0">
                    Klipper reports pending configuration items. Review them independently before manually choosing
                    SAVE_CONFIG; Calibration Center will not send it.
                </v-alert>
            </v-card>

            <v-dialog v-model="showPressureSendConfirm" max-width="560" persistent>
                <v-card>
                    <v-card-title>Arm the reviewed tuning command?</v-card-title>
                    <v-card-text>
                        <v-alert dense text type="warning">
                            This changes runtime pressure advance as the next test print rises in Z. It does not start a
                            file, save configuration, or restart Klipper, but it should be sent only immediately before
                            the exact test print used to choose these values.
                        </v-alert>
                        <code>{{ pressurePreview }}</code>
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer />
                        <v-btn text @click="showPressureSendConfirm = false">Cancel</v-btn>
                        <v-btn color="warning" text :disabled="printerBusy || !pressurePreview" @click="sendPressurePreview">
                            Arm command only
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>

            <v-dialog v-model="showConfirm" max-width="560" persistent>
                <v-card>
                    <v-card-title>{{ confirmationTitle }}</v-card-title>
                    <v-card-text>
                        <v-alert dense text :type="selectedDefinition.heats || selectedDefinition.moves ? 'warning' : 'info'">
                            {{ confirmationWarning }}
                        </v-alert>
                        <p class="mb-2">{{ commandSummary }}</p>
                        <p class="text-caption text--secondary mb-0">
                            This is attended and requires this explicit confirmation. SAVE_CONFIG and printer restarts are
                            never automatic.
                        </p>
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer />
                        <v-btn text @click="showConfirm = false">Cancel</v-btn>
                        <v-btn color="primary" text @click="execute">Confirm and continue</v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
        </template>
    </div>
</template>

<script lang="ts">
import { Component, Mixins, Watch } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import {
    mdiCalculatorVariantOutline,
    mdiChartBellCurveCumulative,
    mdiGrid,
    mdiLayersTripleOutline,
    mdiPlayCircleOutline,
    mdiRefresh,
    mdiStopCircleOutline,
    mdiThermometerLines,
    mdiTuneVariant,
} from '@mdi/js'
import {
    CalibrationCenterFlow,
    CalibrationCenterHeater,
    CalibrationCenterStatus,
} from '@/components/klippertools/types'

interface FlowCard extends CalibrationCenterFlow {
    key: string
    summary: string
    icon: string
}

@Component
export default class CalibrationCenterTool extends Mixins(BaseMixin) {
    mdiPlayCircleOutline = mdiPlayCircleOutline
    mdiRefresh = mdiRefresh
    mdiStopCircleOutline = mdiStopCircleOutline

    selectedFlow = 'pid'
    showConfirm = false
    showPressureSendConfirm = false
    pidHeater = ''
    pidTarget: number | null = null
    meshProfile = ''
    shaperAxis = 'BOTH'
    paStart: number | null = null
    paFactor: number | null = null
    rotationPrevious: number | null = null
    rotationRequested: number | null = null
    rotationActual: number | null = null
    initializedSession = -1

    get status(): CalibrationCenterStatus | null {
        return this.$store.state.printer?.calibration_center ?? null
    }

    get currentValues() {
        return this.status?.current_values ?? {
            pressure_advance: null,
            rotation_distance: null,
            probe_z_offset: null,
            z_endstop_position: null,
            input_shaper: {},
            bed_mesh_profile: null,
            manual_probe: {},
            heaters: [],
            save_config_pending: false,
            save_config_pending_items: {},
        }
    }

    @Watch('status.session_id', { immediate: true })
    initializeFromStatus(): void {
        if (!this.status || this.initializedSession >= 0) return
        const firstHeater = this.currentValues.heaters?.[0]
        this.pidHeater = firstHeater?.name ?? ''
        const rotation = Number(this.currentValues.rotation_distance)
        this.rotationPrevious = Number.isFinite(rotation) && rotation > 0 ? rotation : null
        this.initializedSession = this.status.session_id
    }

    get flowCards(): FlowCard[] {
        const summaries: Record<string, string> = {
            pid: 'Tune one configured heater at a user-supplied target.',
            bed_mesh: 'Run Klipper probing with the printer’s configured mesh settings.',
            z_offset: 'Open Klipper’s attended probe or Z-endstop helper.',
            input_shaper: 'Run Klipper resonance calibration for X, Y, or both.',
            pressure_advance: 'Prepare a reviewed TUNING_TOWER command without arming it.',
            rotation_distance: 'Calculate a corrected value from measured filament travel.',
            first_layer: 'Review prerequisites before starting your own sliced test.',
        }
        const icons: Record<string, string> = {
            pid: mdiThermometerLines,
            bed_mesh: mdiGrid,
            z_offset: mdiLayersTripleOutline,
            input_shaper: mdiChartBellCurveCumulative,
            pressure_advance: mdiTuneVariant,
            rotation_distance: mdiCalculatorVariantOutline,
            first_layer: mdiPlayCircleOutline,
        }
        return Object.entries(this.status?.flows ?? {}).map(([key, flow]) => ({
            ...flow,
            key,
            summary: summaries[key] ?? '',
            icon: icons[key] ?? mdiTuneVariant,
        }))
    }

    get selectedDefinition(): CalibrationCenterFlow {
        return (
            this.status?.flows?.[this.selectedFlow] ?? {
                title: 'Calibration',
                available: false,
                reason: 'Unavailable',
                command: null,
                requires_homing: false,
                attended: true,
                heats: false,
                moves: false,
                permanent_result: false,
            }
        )
    }

    get selectedTitle(): string {
        return this.selectedDefinition.title || 'Calibration'
    }

    get printerBusy(): boolean {
        return ['printing', 'paused'].includes(this.status?.printer_state ?? '')
    }

    get allHomed(): boolean {
        const homed = this.status?.homed_axes ?? ''
        return ['x', 'y', 'z'].every((axis) => homed.includes(axis))
    }

    get requiresHoming(): boolean {
        return Boolean(this.selectedDefinition.requires_homing)
    }

    get manualProbeActive(): boolean {
        return Boolean(this.currentValues.manual_probe?.is_active)
    }

    get selectedHeater(): CalibrationCenterHeater | null {
        return this.currentValues.heaters?.find((heater) => heater.name === this.pidHeater) ?? null
    }

    get heaterChoices(): Array<{ label: string; value: string }> {
        return (this.currentValues.heaters ?? []).map((heater) => ({
            value: heater.name,
            label: `${heater.name} · ${this.numberOrDash(heater.temperature, 1)} °C`,
        }))
    }

    get heaterLimitText(): string {
        if (!this.selectedHeater) return 'Select a configured heater.'
        return `Configured range: ${this.numberOrDash(this.selectedHeater.min_temp, 1)}–${this.numberOrDash(
            this.selectedHeater.max_temp,
            1
        )} °C.`
    }

    get axisChoices(): Array<{ text: string; value: string }> {
        return [
            { text: 'X and Y', value: 'BOTH' },
            { text: 'X only', value: 'X' },
            { text: 'Y only', value: 'Y' },
        ]
    }

    get pressurePreview(): string {
        const result = this.status?.last_result
        if (this.status?.active_flow !== 'pressure_advance' || !result) return ''
        return String(result.command_preview ?? '')
    }

    get canPrepare(): boolean {
        if (!this.status?.ready || this.status.active || this.printerBusy || !this.selectedDefinition.available) return false
        if (this.requiresHoming && !this.allHomed) return false
        if (this.selectedFlow === 'pid') {
            const target = Number(this.pidTarget)
            const heater = this.selectedHeater
            return Boolean(
                heater &&
                    Number.isFinite(target) &&
                    heater.min_temp != null &&
                    heater.max_temp != null &&
                    target > heater.min_temp &&
                    target < heater.max_temp
            )
        }
        if (this.selectedFlow === 'bed_mesh') return !this.meshProfile || /^[A-Za-z0-9_.-]{1,64}$/.test(this.meshProfile)
        if (this.selectedFlow === 'pressure_advance') {
            const start = Number(this.paStart)
            const factor = Number(this.paFactor)
            return Number.isFinite(start) && start >= 0 && start <= 5 && Number.isFinite(factor) && factor > 0 && factor <= 1
        }
        if (this.selectedFlow === 'rotation_distance') {
            return [this.rotationPrevious, this.rotationRequested, this.rotationActual].every(
                (value) => Number.isFinite(Number(value)) && Number(value) > 0
            )
        }
        return true
    }

    get actionLabel(): string {
        if (this.selectedFlow === 'pressure_advance') return 'Prepare command'
        if (this.selectedFlow === 'rotation_distance') return 'Calculate'
        if (this.selectedFlow === 'first_layer') return 'Open guidance'
        return 'Start attended workflow'
    }

    get stateLabel(): string {
        const labels: Record<string, string> = {
            idle: 'Ready',
            running: 'Running',
            guided: 'Guided step',
            review: 'Review',
            error: 'Error',
        }
        return labels[this.status?.state ?? 'idle'] ?? this.status?.state ?? 'Ready'
    }

    get stateColor(): string {
        if (this.status?.state === 'error') return 'error'
        if (this.status?.state === 'review') return 'success'
        if (['running', 'guided'].includes(this.status?.state ?? '')) return 'warning'
        return 'primary'
    }

    get messageType(): 'info' | 'success' | 'warning' {
        if (this.status?.state === 'review') return 'success'
        if (['running', 'guided'].includes(this.status?.state ?? '')) return 'warning'
        return 'info'
    }

    get confirmationTitle(): string {
        return `${this.actionLabel}: ${this.selectedTitle}`
    }

    get confirmationWarning(): string {
        if (this.selectedDefinition.heats && this.selectedDefinition.moves)
            return 'This workflow can heat and move the printer. Clear the machine and remain beside it.'
        if (this.selectedDefinition.heats)
            return 'This workflow heats a configured heater. Remain beside the printer and be ready to stop it.'
        if (this.selectedDefinition.moves)
            return 'This workflow moves the printer. Clear the machine and remain beside it.'
        return 'This workflow does not start printer motion or heat, but its inputs still require review.'
    }

    get commandSummary(): string {
        if (this.selectedFlow === 'pid') return `PID calibration: ${this.pidHeater} at ${Number(this.pidTarget).toFixed(1)} °C.`
        if (this.selectedFlow === 'bed_mesh')
            return this.meshProfile ? `Bed mesh profile: ${this.meshProfile}.` : 'Bed mesh with Klipper’s configured defaults.'
        if (this.selectedFlow === 'input_shaper') return `Input-shaper calibration: ${this.shaperAxis}.`
        if (this.selectedFlow === 'pressure_advance')
            return `Prepare START=${Number(this.paStart).toFixed(6)} and FACTOR=${Number(this.paFactor).toFixed(6)} for review.`
        if (this.selectedFlow === 'rotation_distance')
            return `Calculate ${Number(this.rotationPrevious)} × ${Number(this.rotationActual)} ÷ ${Number(
                this.rotationRequested
            )}.`
        if (this.selectedFlow === 'z_offset') return 'Start Klipper’s interactive Z-offset helper.'
        return 'Show a first-layer review checklist without starting a file.'
    }

    get resultRows(): Record<string, string> {
        const source = this.status?.last_result ?? {}
        return Object.fromEntries(
            Object.entries(source)
                .filter(([key]) => key !== 'command_preview')
                .map(([key, value]) => [key, typeof value === 'number' ? String(value) : String(value ?? '—')])
        )
    }

    execute(): void {
        this.showConfirm = false
        let script = `CALIBRATION_CENTER_START FLOW=${this.selectedFlow} CONFIRM=YES`
        if (this.selectedFlow === 'pid') {
            script += ` HEATER="${this.safeValue(this.pidHeater)}" TARGET=${Number(this.pidTarget).toFixed(3)}`
        } else if (this.selectedFlow === 'bed_mesh' && this.meshProfile) {
            script += ` PROFILE=${this.meshProfile}`
        } else if (this.selectedFlow === 'input_shaper') {
            script += ` AXIS=${this.shaperAxis}`
        } else if (this.selectedFlow === 'pressure_advance') {
            script += ` START=${Number(this.paStart).toFixed(6)} FACTOR=${Number(this.paFactor).toFixed(6)}`
        } else if (this.selectedFlow === 'rotation_distance') {
            script = [
                'CALIBRATION_CENTER_ROTATION_DISTANCE CONFIRM=YES',
                `PREVIOUS=${Number(this.rotationPrevious).toFixed(9)}`,
                `REQUESTED=${Number(this.rotationRequested).toFixed(6)}`,
                `ACTUAL=${Number(this.rotationActual).toFixed(6)}`,
            ].join(' ')
        }
        this.$socket.emit('printer.gcode.script', { script }, { loading: 'calibrationCenterStart' })
    }

    sendPressurePreview(): void {
        if (!this.pressurePreview || this.printerBusy) return
        const script = this.pressurePreview
        this.showPressureSendConfirm = false
        this.$socket.emit(
            'printer.gcode.script',
            { script },
            { loading: 'calibrationCenterPressureAdvance' }
        )
    }

    abort(): void {
        this.$socket.emit(
            'printer.gcode.script',
            { script: 'CALIBRATION_CENTER_ABORT' },
            { loading: 'calibrationCenterAbort' }
        )
    }

    reset(): void {
        this.$socket.emit(
            'printer.gcode.script',
            { script: 'CALIBRATION_CENTER_RESET' },
            { loading: 'calibrationCenterReset' }
        )
    }

    manualStep(direction: '-' | '+'): void {
        this.$socket.emit('printer.gcode.script', { script: `TESTZ Z=${direction}` }, { loading: 'calibrationCenterTestZ' })
    }

    manualAccept(): void {
        this.$socket.emit('printer.gcode.script', { script: 'ACCEPT' }, { loading: 'calibrationCenterAccept' })
    }

    manualAbort(): void {
        this.$socket.emit('printer.gcode.script', { script: 'ABORT' }, { loading: 'calibrationCenterManualAbort' })
    }

    shaperText(axis: 'x' | 'y'): string {
        const values = this.currentValues.input_shaper ?? {}
        const type = values[`shaper_type_${axis}`]
        const frequency = Number(values[`shaper_freq_${axis}`])
        if (!type && !Number.isFinite(frequency)) return '—'
        return `${type ?? 'unknown'}${Number.isFinite(frequency) ? ` · ${frequency.toFixed(1)} Hz` : ''}`
    }

    numberOrDash(value: unknown, digits: number): string {
        const number = Number(value)
        return Number.isFinite(number) ? number.toFixed(digits) : '—'
    }

    safeValue(value: string): string {
        return value.replace(/["\\\r\n]/g, '')
    }

    humanize(value: string): string {
        return value.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
    }
}
</script>

<style scoped>
.calibration-flow {
    background: rgba(127, 127, 127, 0.035);
    border: 1px solid rgba(127, 127, 127, 0.18);
    border-radius: 9px;
    color: inherit;
    cursor: pointer;
    display: block;
    min-height: 132px;
    padding: 12px;
    transition:
        background-color 150ms ease,
        border-color 150ms ease;
    width: 100%;
}

.calibration-flow:hover:not(:disabled),
.calibration-flow--selected {
    background: rgba(33, 150, 243, 0.075);
    border-color: rgba(33, 150, 243, 0.48);
}

.calibration-flow--disabled {
    cursor: not-allowed;
    opacity: 0.62;
}

.value-card {
    background: rgba(127, 127, 127, 0.045);
    border: 1px solid rgba(127, 127, 127, 0.14);
    border-radius: 8px;
    min-height: 64px;
    padding: 9px 10px;
}

.value-card span,
.value-card strong {
    display: block;
}

.value-card span {
    color: rgba(127, 127, 127, 0.9);
    font-size: 0.72rem;
}

.value-card strong {
    font-size: 0.88rem;
    margin-top: 5px;
}

.command-preview code {
    overflow-wrap: anywhere;
    white-space: normal;
}

.result-row {
    align-items: center;
    border-bottom: 1px solid rgba(127, 127, 127, 0.1);
    display: flex;
    gap: 16px;
    justify-content: space-between;
    padding: 6px 0;
}

.result-row:last-child {
    border-bottom: 0;
}

.result-row span {
    color: rgba(127, 127, 127, 0.92);
}
</style>
