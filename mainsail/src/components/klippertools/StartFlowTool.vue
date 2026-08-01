<template>
    <div class="pa-4">
        <template v-if="status && status.stages.length">
            <div class="d-flex justify-space-between text-body-2 mb-2">
                <span>{{ statusText }}</span>
                <span>{{ etaText }}</span>
            </div>
            <v-progress-linear :value="status.progress" :color="progressColor" height="10" rounded class="mb-3" />

            <v-list dense class="transparent pa-0">
                <v-list-item v-for="stage in status.stages" :key="stage.name" class="px-0">
                    <v-list-item-icon class="mr-3">
                        <v-icon :color="stageColor(stage)" small>{{ stageIcon(stage) }}</v-icon>
                    </v-list-item-icon>
                    <v-list-item-content>
                        <v-list-item-title>{{ stageLabel(stage) }}</v-list-item-title>
                    </v-list-item-content>
                    <v-list-item-action-text>{{ stageTime(stage) }}</v-list-item-action-text>
                </v-list-item>
            </v-list>
        </template>

        <v-alert v-else dense text type="info" class="mb-0">
            {{ $t('Panels.KlippertoolsPanel.StartFlow.Waiting') }}
        </v-alert>

        <div v-if="canReset" class="d-flex justify-end mt-2">
            <v-btn small text @click="reset">
                <v-icon small left>{{ mdiRefresh }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Common.Reset') }}
            </v-btn>
        </div>
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { mdiAlertCircle, mdiCheckCircle, mdiClockOutline, mdiProgressClock, mdiRefresh } from '@mdi/js'
import { StartFlowStage, StartFlowStatus } from '@/components/klippertools/types'

@Component
export default class StartFlowTool extends Mixins(BaseMixin) {
    mdiRefresh = mdiRefresh

    get status(): StartFlowStatus | null {
        return this.$store.state.printer?.start_flow ?? null
    }

    get canReset(): boolean {
        return ['complete', 'error'].includes(this.status?.state ?? '')
    }

    get progressColor(): string {
        if (this.status?.state === 'error') return 'error'
        if (this.status?.state === 'complete') return 'success'
        return 'primary'
    }

    get statusText(): string {
        if (!this.status) return ''
        if (this.status.state === 'running' && this.status.current_stage) {
            const stage = this.status.stages.find((item) => item.name === this.status?.current_stage)
            if (stage) return this.stageLabel(stage)
        }
        return String(this.$t(`Panels.KlippertoolsPanel.StartFlow.Status.${this.status.state}`))
    }

    get etaText(): string {
        if (!this.status) return ''
        if (this.status.state === 'complete') {
            return String(
                this.$t('Panels.KlippertoolsPanel.StartFlow.CompletedIn', {
                    time: this.formatDuration(this.status.elapsed_seconds),
                })
            )
        }
        if (this.status.eta_seconds === null) return ''
        return String(
            this.$t('Panels.KlippertoolsPanel.StartFlow.Remaining', {
                time: this.formatDuration(this.status.eta_seconds),
            })
        )
    }

    stageIcon(stage: StartFlowStage): string {
        if (stage.state === 'done') return mdiCheckCircle
        if (stage.state === 'error') return mdiAlertCircle
        if (stage.state === 'active') return mdiProgressClock
        return mdiClockOutline
    }

    stageColor(stage: StartFlowStage): string {
        if (stage.state === 'done') return 'success'
        if (stage.state === 'error') return 'error'
        if (stage.state === 'active') return 'warning'
        return 'grey'
    }

    stageLabel(stage: StartFlowStage): string {
        const key = `Panels.KlippertoolsPanel.StartFlow.Stages.${stage.name}`
        const translated = String(this.$t(key))
        return translated === key ? stage.label : translated
    }

    stageTime(stage: StartFlowStage): string {
        if (stage.duration_seconds !== null) return this.formatDuration(stage.duration_seconds)
        return `~${this.formatDuration(stage.estimate_seconds)}`
    }

    formatDuration(totalSeconds: number): string {
        const seconds = Math.max(0, Math.round(totalSeconds))
        const minutes = Math.floor(seconds / 60)
        const remainder = seconds % 60
        if (minutes > 0) return `${minutes}m ${String(remainder).padStart(2, '0')}s`
        return `${remainder}s`
    }

    reset(): void {
        this.$socket.emit('printer.gcode.script', { script: 'START_FLOW_RESET' }, { loading: 'startFlow' })
    }
}
</script>
