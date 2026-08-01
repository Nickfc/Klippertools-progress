<template>
    <div class="pa-4">
        <v-alert dense text type="warning" class="mb-4">
            {{ $t('Panels.KlippertoolsPanel.Motion.Safety') }}
        </v-alert>

        <v-progress-linear :value="status ? status.progress : 0" color="primary" height="8" rounded class="mb-4" />

        <div class="motion-step mb-3" :class="{ 'motion-step--done': allHomed }">
            <div class="motion-step__number">1</div>
            <div class="motion-step__content">
                <div class="font-weight-medium">{{ $t('Panels.KlippertoolsPanel.Motion.HomeTitle') }}</div>
                <div class="text-caption text--secondary">{{ homedText }}</div>
            </div>
            <v-btn small text :disabled="actionsDisabled" @click="home">
                <v-icon small left>{{ mdiHome }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Motion.Home') }}
            </v-btn>
        </div>

        <div class="motion-step mb-3" :class="{ 'motion-step--done': status && status.noise_complete }">
            <div class="motion-step__number">2</div>
            <div class="motion-step__content">
                <div class="font-weight-medium">{{ $t('Panels.KlippertoolsPanel.Motion.NoiseTitle') }}</div>
                <div class="text-caption text--secondary">{{ noiseText }}</div>
            </div>
            <v-btn small text :disabled="actionsDisabled" @click="noiseTest">
                <v-icon small left>{{ mdiWaveform }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Motion.Test') }}
            </v-btn>
        </div>

        <div class="motion-step mb-4" :class="{ 'motion-step--done': canSave }">
            <div class="motion-step__number">3</div>
            <div class="motion-step__content">
                <div class="font-weight-medium">{{ $t('Panels.KlippertoolsPanel.Motion.CalibrateTitle') }}</div>
                <div class="text-caption text--secondary">
                    {{ $t('Panels.KlippertoolsPanel.Motion.CalibrateHint') }}
                </div>
            </div>
            <div class="d-flex">
                <v-btn small text :disabled="calibrationDisabled" @click="calibrate('X')">X</v-btn>
                <v-btn small text :disabled="calibrationDisabled" @click="calibrate('Y')">Y</v-btn>
            </div>
        </div>

        <v-row dense class="mb-2">
            <v-col v-for="axis in ['x', 'y']" :key="axis" cols="6">
                <v-card outlined class="motion-result-card pa-3" :class="{ 'motion-result-card--ready': result(axis) }">
                    <div class="text-caption text--secondary">{{ axis.toUpperCase() }}</div>
                    <template v-if="result(axis)">
                        <div class="font-weight-medium">{{ result(axis).type }}</div>
                        <div class="text-caption">{{ result(axis).frequency.toFixed(1) }} Hz</div>
                        <v-chip v-if="result(axis).calibrated" x-small color="success" outlined class="mt-1">
                            {{ $t('Panels.KlippertoolsPanel.Motion.NewResult') }}
                        </v-chip>
                    </template>
                    <div v-else class="text--secondary">—</div>
                </v-card>
            </v-col>
        </v-row>

        <v-alert v-if="status && status.error" dense text type="error" class="mt-3 mb-2">
            {{ status.error }}
        </v-alert>

        <div class="d-flex justify-space-between mt-3">
            <v-btn small text :disabled="status && status.active" @click="reset">
                <v-icon small left>{{ mdiRefresh }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Common.Reset') }}
            </v-btn>
            <v-btn small color="primary" :disabled="!canSave" @click="showSave = true">
                <v-icon small left>{{ mdiContentSaveCheck }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Motion.ReviewSave') }}
            </v-btn>
        </div>

        <v-dialog v-model="showSave" max-width="500">
            <v-card>
                <v-card-title>{{ $t('Panels.KlippertoolsPanel.Motion.SaveTitle') }}</v-card-title>
                <v-card-text>{{ $t('Panels.KlippertoolsPanel.Motion.SaveWarning') }}</v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showSave = false">{{ $t('Buttons.Cancel') }}</v-btn>
                    <v-btn color="primary" text @click="saveConfig">
                        {{ $t('Panels.KlippertoolsPanel.Motion.SaveRestart') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { mdiContentSaveCheck, mdiHome, mdiRefresh, mdiWaveform } from '@mdi/js'
import { MotionWizardResult, MotionWizardStatus } from '@/components/klippertools/types'

@Component
export default class MotionWizardTool extends Mixins(BaseMixin) {
    mdiContentSaveCheck = mdiContentSaveCheck
    mdiHome = mdiHome
    mdiRefresh = mdiRefresh
    mdiWaveform = mdiWaveform

    showSave = false

    get status(): MotionWizardStatus | null {
        return this.$store.state.printer?.motion_wizard ?? null
    }

    get printerBusy(): boolean {
        return ['printing', 'paused'].includes(this.$store.state.printer?.print_stats?.state ?? '')
    }

    get allHomed(): boolean {
        const homed = this.status?.homed_axes ?? ''
        return ['x', 'y', 'z'].every((axis) => homed.includes(axis))
    }

    get actionsDisabled(): boolean {
        return this.printerBusy || Boolean(this.status?.active) || !this.status?.ready
    }

    get calibrationDisabled(): boolean {
        return this.actionsDisabled || !this.allHomed
    }

    get canSave(): boolean {
        return Boolean(
            this.status?.pending_save &&
            this.status.completed_axes.includes('x') &&
            this.status.completed_axes.includes('y') &&
            !this.status.active
        )
    }

    get homedText(): string {
        const key = this.allHomed ? 'Homed' : 'NotHomed'
        return String(this.$t(`Panels.KlippertoolsPanel.Motion.${key}`))
    }

    get noiseText(): string {
        const key = this.status?.noise_complete ? 'NoiseComplete' : 'NoiseHint'
        return String(this.$t(`Panels.KlippertoolsPanel.Motion.${key}`))
    }

    result(axis: string): MotionWizardResult | null {
        return this.status?.results?.[axis] ?? null
    }

    home(): void {
        this.$socket.emit('printer.gcode.script', { script: 'G28' }, { loading: 'motionWizardHome' })
    }

    noiseTest(): void {
        this.$socket.emit('printer.gcode.script', { script: 'MOTION_WIZARD_NOISE' }, { loading: 'motionWizardNoise' })
    }

    calibrate(axis: 'X' | 'Y'): void {
        this.$socket.emit(
            'printer.gcode.script',
            { script: `MOTION_WIZARD_CALIBRATE AXIS=${axis}` },
            { loading: `motionWizard${axis}` }
        )
    }

    reset(): void {
        this.$socket.emit('printer.gcode.script', { script: 'MOTION_WIZARD_RESET' }, { loading: 'motionWizardReset' })
    }

    saveConfig(): void {
        this.showSave = false
        this.$socket.emit('printer.gcode.script', { script: 'SAVE_CONFIG' }, { loading: 'topbarSaveConfig' })
    }
}
</script>

<style scoped>
.motion-step {
    align-items: center;
    border: 1px solid rgba(127, 127, 127, 0.16);
    border-radius: 8px;
    display: flex;
    gap: 12px;
    padding: 9px 10px;
    background: rgba(127, 127, 127, 0.045);
    transition:
        background-color 160ms ease,
        border-color 160ms ease;
}

.motion-step--done {
    border-color: rgba(76, 175, 80, 0.3);
    background: rgba(76, 175, 80, 0.055);
}

.motion-step__number {
    align-items: center;
    background: rgba(33, 150, 243, 0.16);
    border-radius: 50%;
    color: #42a5f5;
    display: flex;
    flex: 0 0 28px;
    font-size: 0.8rem;
    font-weight: 700;
    height: 28px;
    justify-content: center;
}

.motion-step__content {
    flex: 1 1 auto;
    min-width: 0;
}

.motion-step--done .motion-step__number {
    background: rgba(76, 175, 80, 0.16);
    color: #66bb6a;
}

.motion-result-card {
    min-height: 92px;
    background: rgba(127, 127, 127, 0.035) !important;
    transition:
        background-color 160ms ease,
        border-color 160ms ease;
}

.motion-result-card--ready {
    border-color: rgba(33, 150, 243, 0.34) !important;
    background: rgba(33, 150, 243, 0.06) !important;
}
</style>
