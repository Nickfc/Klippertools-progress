<template>
    <div class="pa-4">
        <div class="d-flex justify-end mb-2">
            <v-btn small text color="primary" @click="showAddDialog = true">
                <v-icon small left>{{ mdiPlus }}</v-icon>
                {{ $t('Panels.KlippertoolsPanel.Maintenance.AddTask') }}
            </v-btn>
        </div>

        <v-list v-if="activeEntries.length" dense class="transparent pa-0">
            <v-list-item
                v-for="entry in activeEntries"
                :key="entry.id"
                class="maintenance-entry px-0"
                @click="openDetails(entry)">
                <v-list-item-content>
                    <div class="d-flex justify-space-between mb-1">
                        <v-list-item-title>{{ entry.name }}</v-list-item-title>
                        <span :class="entryStatusClass(entry)" class="text-caption">{{ entryStatus(entry) }}</span>
                    </div>
                    <v-progress-linear
                        :value="entryProgress(entry)"
                        :color="entryProgress(entry) >= 100 ? 'error' : 'primary'"
                        height="7"
                        rounded />
                    <div class="text-caption text--secondary mt-1">{{ entryMetric(entry) }}</div>
                </v-list-item-content>
                <v-list-item-icon class="ml-3 mr-0">
                    <v-icon small>{{ mdiChevronRight }}</v-icon>
                </v-list-item-icon>
            </v-list-item>
        </v-list>

        <v-alert v-else dense text type="info" class="mb-0">
            {{ $t('Panels.KlippertoolsPanel.Maintenance.Empty') }}
        </v-alert>

        <history-list-panel-add-maintenance v-model="showAddDialog" />
        <history-list-panel-detail-maintenance v-if="selectedEntry" v-model="showDetailDialog" :item="selectedEntry" />
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import HistoryListPanelAddMaintenance from '@/components/dialogs/HistoryListPanelAddMaintenance.vue'
import HistoryListPanelDetailMaintenance from '@/components/dialogs/HistoryListPanelDetailMaintenance.vue'
import { GuiMaintenanceStateEntry } from '@/store/gui/maintenance/types'
import { mdiChevronRight, mdiPlus } from '@mdi/js'

interface MaintenanceMetric {
    progress: number
    text: string
}

@Component({
    components: {
        HistoryListPanelAddMaintenance,
        HistoryListPanelDetailMaintenance,
    },
})
export default class MaintenanceTrackerTool extends Mixins(BaseMixin) {
    mdiChevronRight = mdiChevronRight
    mdiPlus = mdiPlus

    showAddDialog = false
    showDetailDialog = false
    selectedEntry: GuiMaintenanceStateEntry | null = null

    get entries(): GuiMaintenanceStateEntry[] {
        return this.$store.getters['gui/maintenance/getEntries'] ?? []
    }

    get activeEntries(): GuiMaintenanceStateEntry[] {
        return this.entries
            .filter((entry) => entry.end_time === null && entry.reminder?.type !== null)
            .sort((left, right) => this.entryProgress(right) - this.entryProgress(left))
    }

    get totalPrintTime(): number {
        return this.$store.state.server.history.job_totals?.total_print_time ?? 0
    }

    get totalFilament(): number {
        return this.$store.state.server.history.job_totals?.total_filament_used ?? 0
    }

    metrics(entry: GuiMaintenanceStateEntry): MaintenanceMetric[] {
        const metrics: MaintenanceMetric[] = []
        if (entry.reminder.printtime.bool && entry.reminder.printtime.value) {
            const used = Math.max(0, (this.totalPrintTime - entry.start_printtime) / 3600)
            const target = entry.reminder.printtime.value
            metrics.push({
                progress: (used / target) * 100,
                text: `${used.toFixed(1)} / ${target} h`,
            })
        }
        if (entry.reminder.filament.bool && entry.reminder.filament.value) {
            const used = Math.max(0, (this.totalFilament - entry.start_filament) / 1000)
            const target = entry.reminder.filament.value
            metrics.push({
                progress: (used / target) * 100,
                text: `${used.toFixed(0)} / ${target} m`,
            })
        }
        if (entry.reminder.date.bool && entry.reminder.date.value) {
            const used = Math.max(0, Date.now() / 1000 - entry.start_time) / 86400
            const target = entry.reminder.date.value
            metrics.push({
                progress: (used / target) * 100,
                text: String(
                    this.$t('Panels.KlippertoolsPanel.Maintenance.DaysProgress', {
                        current: used.toFixed(0),
                        total: target,
                    })
                ),
            })
        }
        return metrics
    }

    primaryMetric(entry: GuiMaintenanceStateEntry): MaintenanceMetric | null {
        const metrics = this.metrics(entry)
        if (!metrics.length) return null
        return metrics.reduce((highest, metric) => (metric.progress > highest.progress ? metric : highest))
    }

    entryProgress(entry: GuiMaintenanceStateEntry): number {
        return Math.min(100, Math.max(0, this.primaryMetric(entry)?.progress ?? 0))
    }

    entryMetric(entry: GuiMaintenanceStateEntry): string {
        return this.primaryMetric(entry)?.text ?? ''
    }

    entryStatus(entry: GuiMaintenanceStateEntry): string {
        const key = this.entryProgress(entry) >= 100 ? 'Due' : 'Tracking'
        return String(this.$t(`Panels.KlippertoolsPanel.Maintenance.${key}`))
    }

    entryStatusClass(entry: GuiMaintenanceStateEntry): string {
        return this.entryProgress(entry) >= 100 ? 'error--text font-weight-bold' : 'text--secondary'
    }

    openDetails(entry: GuiMaintenanceStateEntry): void {
        this.selectedEntry = entry
        this.showDetailDialog = true
    }
}
</script>

<style scoped>
.maintenance-entry {
    cursor: pointer;
}
</style>
