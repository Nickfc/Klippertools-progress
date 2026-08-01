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
import { mdiProgressClock, mdiShieldCheckOutline, mdiToolboxOutline, mdiTuneVariant, mdiWrenchClock } from '@mdi/js'

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
    mdiProgressClock = mdiProgressClock
    mdiShieldCheckOutline = mdiShieldCheckOutline
    mdiToolboxOutline = mdiToolboxOutline
    mdiTuneVariant = mdiTuneVariant
    mdiWrenchClock = mdiWrenchClock

    tab = 0

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
}
</script>

<style scoped>
@media (max-width: 520px) {
    .klippertools-tab-label {
        display: none;
    }
}
</style>
