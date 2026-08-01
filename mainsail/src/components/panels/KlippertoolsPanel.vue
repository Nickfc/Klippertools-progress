<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiToolboxOutline"
        :title="$t('Panels.KlippertoolsPanel.Headline')"
        :collapsible="true"
        card-class="klippertools-panel"
        :hide-buttons-on-collapse="true">
        <template #buttons-title>
            <v-chip v-if="attentionCount" x-small color="error" outlined class="ml-2">
                {{ $t('Panels.KlippertoolsPanel.Attention', { count: attentionCount }) }}
            </v-chip>
            <v-btn
                v-if="updaterAvailable"
                icon
                small
                class="ml-1"
                :loading="updateStatus.updating"
                :disabled="printerIsPrinting"
                :aria-label="$t('Panels.KlippertoolsPanel.Update.Title')"
                @click.stop="openUpdateDialog">
                <v-icon small>{{ mdiCloudDownloadOutline }}</v-icon>
            </v-btn>
        </template>

        <v-tabs v-model="tab" grow show-arrows background-color="transparent" color="primary">
            <v-tab :aria-label="$t('Panels.KlippertoolsPanel.Tabs.Guard')">
                <v-icon small class="mr-1">{{ mdiShieldCheckOutline }}</v-icon>
                <span class="klippertools-tab-label">{{ $t('Panels.KlippertoolsPanel.Tabs.Guard') }}</span>
            </v-tab>
            <v-tab :aria-label="$t('Panels.KlippertoolsPanel.Tabs.Start')">
                <v-icon small class="mr-1">{{ mdiProgressClock }}</v-icon>
                <span class="klippertools-tab-label">{{ $t('Panels.KlippertoolsPanel.Tabs.Start') }}</span>
            </v-tab>
            <v-tab :aria-label="$t('Panels.KlippertoolsPanel.Tabs.Maintenance')">
                <v-icon small class="mr-1">{{ mdiWrenchClock }}</v-icon>
                <span class="klippertools-tab-label">{{ $t('Panels.KlippertoolsPanel.Tabs.Maintenance') }}</span>
            </v-tab>
            <v-tab :aria-label="$t('Panels.KlippertoolsPanel.Tabs.Motion')">
                <v-icon small class="mr-1">{{ mdiTuneVariant }}</v-icon>
                <span class="klippertools-tab-label">{{ $t('Panels.KlippertoolsPanel.Tabs.Motion') }}</span>
            </v-tab>
        </v-tabs>

        <v-divider />

        <v-tabs-items v-model="tab" class="transparent">
            <v-tab-item><nozzle-guard-tool /></v-tab-item>
            <v-tab-item><start-flow-tool /></v-tab-item>
            <v-tab-item><maintenance-tracker-tool /></v-tab-item>
            <v-tab-item><motion-wizard-tool /></v-tab-item>
        </v-tabs-items>

        <v-dialog v-model="showUpdateDialog" max-width="520">
            <v-card>
                <v-card-title>{{ $t('Panels.KlippertoolsPanel.Update.Title') }}</v-card-title>
                <v-card-text>
                    <v-alert v-if="printerIsPrinting" dense text type="warning">
                        {{ $t('Panels.KlippertoolsPanel.Update.PrintingBlocked') }}
                    </v-alert>
                    <p>{{ $t('Panels.KlippertoolsPanel.Update.Description') }}</p>
                    <div class="text-caption text--secondary">
                        {{ $t('Panels.KlippertoolsPanel.Update.Installed', { version: installedVersion }) }}
                    </div>
                    <v-progress-linear
                        v-if="updateStatus.updating"
                        indeterminate
                        color="primary"
                        class="mt-4" />
                    <v-alert
                        v-if="updateStatus.message"
                        :type="updateStatus.state === 'error' ? 'error' : updateStatus.state === 'complete' ? 'success' : 'info'"
                        dense
                        text
                        class="mt-4 mb-0">
                        {{ updateStatus.message }}
                    </v-alert>
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text :disabled="updateStatus.updating" @click="showUpdateDialog = false">
                        {{ $t('Buttons.Cancel') }}
                    </v-btn>
                    <v-btn
                        color="primary"
                        text
                        :loading="updateStatus.updating"
                        :disabled="printerIsPrinting || updateStatus.updating"
                        @click="startUpdate">
                        {{ $t('Panels.KlippertoolsPanel.Update.Action') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import Panel from '@/components/ui/Panel.vue'
import MaintenanceTrackerTool from '@/components/klippertools/MaintenanceTrackerTool.vue'
import MotionWizardTool from '@/components/klippertools/MotionWizardTool.vue'
import NozzleGuardTool from '@/components/klippertools/NozzleGuardTool.vue'
import StartFlowTool from '@/components/klippertools/StartFlowTool.vue'
import {
    mdiCloudDownloadOutline,
    mdiProgressClock,
    mdiShieldCheckOutline,
    mdiToolboxOutline,
    mdiTuneVariant,
    mdiWrenchClock,
} from '@mdi/js'

interface UpdateStatus {
    state: string
    message: string
    installed_version: string
    updating: boolean
    restart_required?: boolean
}

@Component({
    components: {
        MaintenanceTrackerTool,
        MotionWizardTool,
        NozzleGuardTool,
        Panel,
        StartFlowTool,
    },
})
export default class KlippertoolsPanel extends Mixins(BaseMixin) {
    mdiCloudDownloadOutline = mdiCloudDownloadOutline
    mdiProgressClock = mdiProgressClock
    mdiShieldCheckOutline = mdiShieldCheckOutline
    mdiToolboxOutline = mdiToolboxOutline
    mdiTuneVariant = mdiTuneVariant
    mdiWrenchClock = mdiWrenchClock

    tab = 0
    showUpdateDialog = false
    updateTimer: number | null = null
    updateStatus: UpdateStatus = {
        state: 'idle',
        message: '',
        installed_version: 'unknown',
        updating: false,
    }

    mounted(): void {
        if (this.updaterAvailable) this.refreshUpdateStatus()
    }

    beforeDestroy(): void {
        this.stopUpdatePolling()
    }

    get available(): boolean {
        return Boolean(
            this.$store.state.printer?.nozzle_guard ||
            this.$store.state.printer?.start_flow ||
            this.$store.state.printer?.motion_wizard
        )
    }

    get attentionCount(): number {
        const nozzleMismatch = this.$store.state.printer?.nozzle_guard?.blocking ? 1 : 0
        const maintenance = this.$store.getters['gui/maintenance/getOverdueEntries']?.length ?? 0
        return nozzleMismatch + maintenance
    }

    get updaterAvailable(): boolean {
        return this.moonrakerComponents.includes('klippertools')
    }

    get installedVersion(): string {
        return this.updateStatus.installed_version || 'unknown'
    }

    async openUpdateDialog(): Promise<void> {
        this.showUpdateDialog = true
        await this.refreshUpdateStatus()
    }

    async refreshUpdateStatus(): Promise<void> {
        if (!this.updaterAvailable || !this.socketIsConnected) return
        try {
            const status = await this.$socket.emitAndWait('machine.klippertools.status', {})
            this.updateStatus = { ...this.updateStatus, ...status }
            if (!this.updateStatus.updating) this.stopUpdatePolling()
        } catch (error) {
            this.updateStatus = {
                ...this.updateStatus,
                state: 'error',
                message: this.errorMessage(error),
                updating: false,
            }
            this.stopUpdatePolling()
        }
    }

    async startUpdate(): Promise<void> {
        this.updateStatus = {
            ...this.updateStatus,
            state: 'starting',
            message: String(this.$t('Panels.KlippertoolsPanel.Update.Starting')),
            updating: true,
        }
        try {
            await this.$socket.emitAndWait('machine.klippertools.update', {})
            this.startUpdatePolling()
        } catch (error) {
            this.updateStatus = {
                ...this.updateStatus,
                state: 'error',
                message: this.errorMessage(error),
                updating: false,
            }
        }
    }

    startUpdatePolling(): void {
        this.stopUpdatePolling()
        this.updateTimer = window.setInterval(() => this.refreshUpdateStatus(), 1500)
    }

    stopUpdatePolling(): void {
        if (this.updateTimer !== null) window.clearInterval(this.updateTimer)
        this.updateTimer = null
    }

    errorMessage(error: unknown): string {
        if (typeof error === 'object' && error !== null && 'message' in error) {
            return String((error as { message: unknown }).message)
        }
        return String(this.$t('Panels.KlippertoolsPanel.Update.Failed'))
    }
}
</script>

<style scoped>
@media (max-width: 520px) {
    .klippertools-tab-label {
        display: none;
    }
}
</style>
