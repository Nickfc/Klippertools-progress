<template>
    <div class="pa-4">
        <v-alert dense text :type="alertType" class="mb-4">
            {{ stateText }}
        </v-alert>

        <div v-if="status" class="klippertools-comparison mb-3">
            <div>
                <div class="text-caption text--secondary">
                    {{ $t('Panels.KlippertoolsPanel.NozzleGuard.KlipperNozzle') }}
                </div>
                <div class="text-h5">{{ formatNozzle(status.configured_nozzle) }}</div>
            </div>
            <v-icon :color="comparisonColor">{{ comparisonIcon }}</v-icon>
            <div class="text-right">
                <div class="text-caption text--secondary">
                    {{ $t('Panels.KlippertoolsPanel.NozzleGuard.FileNozzle') }}
                </div>
                <div class="text-h5">{{ detectedNozzleText }}</div>
            </div>
        </div>

        <div v-if="status && status.filename" class="text-caption text--secondary text-truncate mb-3">
            {{ status.filename }}
        </div>

        <div class="d-flex flex-wrap justify-end ga-2">
            <v-btn v-if="canRecheck" small text :disabled="isBusy" @click="recheck">
                <v-icon small left>{{ mdiRefresh }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.NozzleGuard.Recheck') }}
            </v-btn>
            <v-btn v-if="canOverride" small color="error" text :disabled="isBusy" @click="showOverride = true">
                <v-icon small left>{{ mdiShieldOffOutline }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.NozzleGuard.Override') }}
            </v-btn>
        </div>

        <v-dialog v-model="showOverride" max-width="480">
            <v-card>
                <v-card-title>{{ $t('Panels.KlippertoolsPanel.NozzleGuard.OverrideTitle') }}</v-card-title>
                <v-card-text>
                    {{ $t('Panels.KlippertoolsPanel.NozzleGuard.OverrideWarning') }}
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showOverride = false">{{ $t('Buttons.Cancel') }}</v-btn>
                    <v-btn color="error" text @click="overrideMismatch">
                        {{ $t('Panels.KlippertoolsPanel.NozzleGuard.OverrideOnce') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { mdiAlertCircle, mdiCheckCircle, mdiHelpCircle, mdiRefresh, mdiShieldOffOutline } from '@mdi/js'
import { NozzleGuardStatus } from '@/components/klippertools/types'

@Component
export default class NozzleGuardTool extends Mixins(BaseMixin) {
    mdiRefresh = mdiRefresh
    mdiShieldOffOutline = mdiShieldOffOutline

    showOverride = false

    get status(): NozzleGuardStatus | null {
        return this.$store.state.printer?.nozzle_guard ?? null
    }

    get isBusy(): boolean {
        return ['printing', 'paused'].includes(this.$store.state.printer?.print_stats?.state ?? '')
    }

    get canRecheck(): boolean {
        return Boolean(this.status?.filename)
    }

    get canOverride(): boolean {
        return this.status?.state === 'mismatch' && this.status.blocking
    }

    get alertType(): 'success' | 'warning' | 'error' | 'info' {
        if (this.status?.state === 'match') return 'success'
        if (this.status?.state === 'mismatch') return this.status.blocking ? 'error' : 'warning'
        if (this.status?.state === 'error') return 'error'
        if (this.status?.state === 'overridden') return 'warning'
        return 'info'
    }

    get comparisonColor(): string {
        if (this.status?.state === 'match') return 'success'
        if (this.status?.state === 'mismatch') return 'error'
        return 'grey'
    }

    get comparisonIcon(): string {
        if (this.status?.state === 'match') return mdiCheckCircle
        if (this.status?.state === 'mismatch') return mdiAlertCircle
        return mdiHelpCircle
    }

    get detectedNozzleText(): string {
        const values = this.status?.detected_nozzles ?? []
        if (!values.length) return String(this.$t('Panels.KlippertoolsPanel.Common.Unknown'))
        return values.map((value) => this.formatNozzle(value)).join(', ')
    }

    get stateText(): string {
        const state = this.status?.state ?? 'no_file'
        if (state === 'mismatch') {
            const key = this.status?.blocking ? 'mismatch_blocked' : 'mismatch_warning'
            return String(this.$t(`Panels.KlippertoolsPanel.NozzleGuard.States.${key}`))
        }
        return String(this.$t(`Panels.KlippertoolsPanel.NozzleGuard.States.${state}`))
    }

    formatNozzle(value: number): string {
        return `${value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')} mm`
    }

    recheck(): void {
        this.$socket.emit('printer.gcode.script', { script: 'NOZZLE_GUARD_RECHECK' }, { loading: 'nozzleGuard' })
    }

    overrideMismatch(): void {
        this.showOverride = false
        this.$socket.emit('printer.gcode.script', { script: 'NOZZLE_GUARD_OVERRIDE' }, { loading: 'nozzleGuard' })
    }
}
</script>

<style scoped>
.klippertools-comparison {
    align-items: center;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    gap: 16px;
}

.ga-2 {
    gap: 8px;
}
</style>
