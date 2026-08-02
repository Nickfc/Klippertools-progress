<template>
    <v-container fluid class="service-manager py-0">
        <div class="d-flex flex-wrap align-center justify-space-between mb-4">
            <div>
                <h1 class="text-h5 mb-1">Klippertools Service Manager</h1>
                <div class="text-body-2 text--secondary">
                    Usage-based maintenance with editable recommended starting points.
                </div>
            </div>
            <div class="d-flex mt-2 mt-sm-0">
                <v-btn outlined small color="primary" class="mr-2" @click="editTask()">
                    <v-icon small left>{{ mdiPlus }}</v-icon>
                    Add task
                </v-btn>
                <v-btn outlined small @click="refresh">
                    <v-icon small left>{{ mdiRefresh }}</v-icon>
                    Refresh
                </v-btn>
            </div>
        </div>

        <v-alert dense text type="info" class="mb-4">
            Motion is commanded Klipper travel, not encoder feedback. Recommended intervals are conservative starting
            points—inspect sooner after crashes, contamination, noise, looseness, or changed print quality.
        </v-alert>
        <v-alert v-if="pageError" dense text type="error" dismissible class="mb-4" @input="pageError = ''">
            {{ pageError }}
        </v-alert>
        <v-progress-linear v-if="loading && !status" indeterminate color="primary" class="mb-4" />

        <v-card v-if="thermalAvailable" outlined class="thermal-soak-card mb-4">
            <v-card-title class="pb-0">
                <div>
                    <div class="text-subtitle-1">Thermal Soak Assistant</div>
                    <div class="text-caption text--secondary">
                        Wait for measured temperature stability instead of a fixed timer.
                    </div>
                </div>
            </v-card-title>
            <thermal-soak-tool />
        </v-card>

        <template v-if="status">
            <v-row dense class="mb-2">
                <v-col v-for="counter in counterCards" :key="counter.key" cols="6" sm="4" lg="3" xl="2">
                    <v-card outlined class="counter-card pa-3 h-100">
                        <div class="text-caption text--secondary">{{ counter.label }}</div>
                        <div class="text-h6">{{ counter.value }}</div>
                        <div v-if="counter.note" class="text-caption text--secondary">
                            {{ counter.note }}
                        </div>
                    </v-card>
                </v-col>
            </v-row>

            <v-tabs v-model="tab" background-color="transparent" class="mb-3">
                <v-tab>Schedule</v-tab>
                <v-tab>History</v-tab>
                <v-tab>Settings</v-tab>
            </v-tabs>

            <v-tabs-items v-model="tab" class="transparent">
                <v-tab-item>
                    <div class="d-flex align-center justify-space-between mb-3">
                        <div>
                            <div class="text-subtitle-1 font-weight-medium">Upcoming and overdue</div>
                            <div class="text-caption text--secondary">
                                Tasks are sorted by urgency. Any enabled threshold can make a task due.
                            </div>
                        </div>
                        <v-chip small outlined :color="dueCount ? 'error' : 'success'">{{ dueCount }} due</v-chip>
                    </div>
                    <v-row dense>
                        <v-col v-for="task in status.tasks" :key="task.id" cols="12" lg="6">
                            <v-card outlined class="task-card h-100" :class="`task-card--${task.state}`">
                                <v-card-title class="pb-2">
                                    <div class="flex-grow-1">
                                        <div class="text-subtitle-1">{{ task.name }}</div>
                                        <div class="text-caption text--secondary">
                                            {{ task.area }}
                                        </div>
                                    </div>
                                    <v-chip small outlined :color="taskColor(task)">
                                        {{ task.state === 'due' ? 'Due' : task.state === 'soon' ? 'Soon' : 'Good' }}
                                    </v-chip>
                                </v-card-title>
                                <v-card-text>
                                    <v-progress-linear
                                        :value="Math.min(100, task.progress * 100)"
                                        :color="taskColor(task)"
                                        rounded
                                        height="8"
                                        class="mb-3" />
                                    <div class="metric-grid">
                                        <div
                                            v-for="metric in task.metrics"
                                            :key="metric.metric"
                                            class="metric-row"
                                            :class="{ 'metric-row--due': metric.due }">
                                            <span>{{ metric.label }}</span>
                                            <strong>{{ remaining(metric) }}</strong>
                                        </div>
                                    </div>
                                    <v-expansion-panels flat class="mt-2">
                                        <v-expansion-panel>
                                            <v-expansion-panel-header class="px-0 py-1 text-caption">
                                                Service instructions
                                            </v-expansion-panel-header>
                                            <v-expansion-panel-content class="instructions">
                                                {{ task.instructions }}
                                            </v-expansion-panel-content>
                                        </v-expansion-panel>
                                    </v-expansion-panels>
                                </v-card-text>
                                <v-card-actions>
                                    <v-btn small text @click="editTask(task)">
                                        <v-icon small left>{{ mdiPencilOutline }}</v-icon>
                                        Edit
                                    </v-btn>
                                    <v-btn small text @click="snooze(task, '24h')">Snooze 24h</v-btn>
                                    <v-spacer />
                                    <v-btn small text color="success" @click="markServiced(task)">
                                        <v-icon small left>{{ mdiCheck }}</v-icon>
                                        Mark serviced
                                    </v-btn>
                                </v-card-actions>
                            </v-card>
                        </v-col>
                    </v-row>
                </v-tab-item>

                <v-tab-item>
                    <v-card outlined>
                        <v-card-title class="text-subtitle-1">Service history</v-card-title>
                        <v-list v-if="status.history.length" two-line>
                            <v-list-item v-for="(entry, index) in status.history" :key="`${entry.at}-${index}`">
                                <v-list-item-icon>
                                    <v-icon>
                                        {{ entry.type === 'serviced' ? mdiCheckCircleOutline : mdiHistory }}
                                    </v-icon>
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>{{ historyTitle(entry) }}</v-list-item-title>
                                    <v-list-item-subtitle>
                                        {{ dateTime(entry.at) }}
                                        <span v-if="entry.note">· {{ entry.note }}</span>
                                    </v-list-item-subtitle>
                                </v-list-item-content>
                            </v-list-item>
                        </v-list>
                        <v-card-text v-else class="text--secondary">
                            History starts when a task is marked serviced or settings are reset/imported.
                        </v-card-text>
                    </v-card>
                </v-tab-item>

                <v-tab-item>
                    <v-row dense>
                        <v-col cols="12" md="6">
                            <v-card outlined class="h-100">
                                <v-card-title class="text-subtitle-1">Recommended schedule</v-card-title>
                                <v-card-text>
                                    Restore the ten Ender 7 starting presets and remove custom tasks or interval
                                    overrides. Existing service baselines and history are preserved.
                                </v-card-text>
                                <v-card-actions>
                                    <v-btn text color="primary" @click="showRecommendedReset = true">
                                        Reset to recommended
                                    </v-btn>
                                </v-card-actions>
                            </v-card>
                        </v-col>
                        <v-col cols="12" md="6">
                            <v-card outlined class="h-100">
                                <v-card-title class="text-subtitle-1">Import and export</v-card-title>
                                <v-card-text>
                                    Export tasks and history as JSON, or import a previously exported task schedule.
                                    Lifetime counters are never imported.
                                </v-card-text>
                                <v-card-actions>
                                    <v-btn text color="primary" @click="exportData">Export JSON</v-btn>
                                    <v-btn text color="primary" @click="$refs.importInput.click()">Import JSON</v-btn>
                                    <input
                                        ref="importInput"
                                        type="file"
                                        accept="application/json,.json"
                                        hidden
                                        @change="importData" />
                                </v-card-actions>
                            </v-card>
                        </v-col>
                        <v-col cols="12">
                            <v-card outlined class="danger-zone">
                                <v-card-title class="text-subtitle-1 error--text">
                                    Advanced: lifetime counters
                                </v-card-title>
                                <v-card-text>
                                    This resets every lifetime usage counter and every task baseline. It is blocked
                                    while printing and service history records the reset.
                                </v-card-text>
                                <v-card-actions>
                                    <v-btn text color="error" @click="showCounterReset = true">
                                        Reset lifetime counters
                                    </v-btn>
                                </v-card-actions>
                            </v-card>
                        </v-col>
                    </v-row>
                </v-tab-item>
            </v-tabs-items>
        </template>

        <v-dialog v-model="showEditDialog" max-width="720" persistent>
            <v-card>
                <v-card-title>{{ draft.id ? 'Edit service task' : 'Add service task' }}</v-card-title>
                <v-card-text>
                    <v-text-field v-model="draft.name" label="Name" outlined dense />
                    <v-text-field v-model="draft.area" label="Service area" outlined dense />
                    <v-textarea v-model="draft.instructions" label="Instructions" outlined rows="3" />
                    <div class="d-flex align-center justify-space-between mb-2">
                        <div class="font-weight-medium">Countdowns</div>
                        <v-btn small text color="primary" @click="addThreshold">
                            <v-icon small left>{{ mdiPlus }}</v-icon>
                            Add countdown
                        </v-btn>
                    </div>
                    <div v-for="(threshold, index) in draft.thresholds" :key="index" class="threshold-row">
                        <v-select
                            v-model="threshold.metric"
                            :items="metricChoices"
                            item-text="text"
                            item-value="value"
                            label="Usage metric"
                            outlined
                            dense
                            hide-details
                            @change="threshold.value = defaultDisplayValue(threshold.metric)" />
                        <v-text-field
                            v-model.number="threshold.value"
                            type="number"
                            min="0"
                            :suffix="displayUnit(threshold.metric)"
                            label="Interval"
                            outlined
                            dense
                            hide-details />
                        <v-btn icon color="error" @click="draft.thresholds.splice(index, 1)">
                            <v-icon>{{ mdiDeleteOutline }}</v-icon>
                        </v-btn>
                    </div>
                    <v-alert v-if="editError" dense text type="error" class="mt-3 mb-0">{{ editError }}</v-alert>
                </v-card-text>
                <v-card-actions>
                    <v-btn v-if="draft.id" text color="error" @click="deleteDraft">Delete</v-btn>
                    <v-spacer />
                    <v-btn text @click="showEditDialog = false">Cancel</v-btn>
                    <v-btn text color="primary" @click="saveDraft">Save</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="showRecommendedReset" max-width="520">
            <v-card>
                <v-card-title>Reset recommended schedule?</v-card-title>
                <v-card-text>
                    Custom tasks and interval overrides will be removed. Service history and current task baselines are
                    preserved.
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showRecommendedReset = false">Cancel</v-btn>
                    <v-btn text color="primary" @click="resetRecommended">Reset schedule</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <v-dialog v-model="showCounterReset" max-width="560">
            <v-card>
                <v-card-title class="error--text">Reset all lifetime counters?</v-card-title>
                <v-card-text>
                    <p>
                        This cannot be undone from the UI. Type
                        <strong>RESET LIFETIME COUNTERS</strong>
                        to continue.
                    </p>
                    <v-text-field v-model="resetConfirmation" outlined dense />
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showCounterReset = false">Cancel</v-btn>
                    <v-btn
                        text
                        color="error"
                        :disabled="resetConfirmation !== 'RESET LIFETIME COUNTERS'"
                        @click="resetCounters">
                        Reset counters
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </v-container>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import ThermalSoakTool from '@/components/klippertools/ThermalSoakTool.vue'
import {
    ServiceHistoryEntry,
    ServiceManagerStatus,
    ServiceMetricKey,
    ServiceMetricStatus,
    ServiceTask,
} from '@/components/klippertools/types'
import {
    mdiCheck,
    mdiCheckCircleOutline,
    mdiDeleteOutline,
    mdiHistory,
    mdiPencilOutline,
    mdiPlus,
    mdiRefresh,
} from '@mdi/js'

interface DraftThreshold {
    metric: ServiceMetricKey
    value: number
}
interface TaskDraft {
    id: string
    name: string
    area: string
    instructions: string
    recommended: boolean
    thresholds: DraftThreshold[]
}

@Component({ components: { ThermalSoakTool } })
export default class PageKlippertools extends Mixins(BaseMixin) {
    mdiCheck = mdiCheck
    mdiCheckCircleOutline = mdiCheckCircleOutline
    mdiDeleteOutline = mdiDeleteOutline
    mdiHistory = mdiHistory
    mdiPencilOutline = mdiPencilOutline
    mdiPlus = mdiPlus
    mdiRefresh = mdiRefresh
    status: ServiceManagerStatus | null = null
    loading = false
    tab = 0
    timer: number | null = null
    showEditDialog = false
    showRecommendedReset = false
    showCounterReset = false
    resetConfirmation = ''
    editError = ''
    pageError = ''
    draft: TaskDraft = this.emptyDraft()

    mounted(): void {
        this.refresh()
        this.timer = window.setInterval(() => this.refresh(), 5000)
    }
    beforeDestroy(): void {
        if (this.timer !== null) window.clearInterval(this.timer)
    }

    get dueCount(): number {
        return this.status?.tasks.filter((task) => task.due).length ?? 0
    }
    get thermalAvailable(): boolean {
        return Boolean(this.$store.state.printer?.thermal_soak?.ready)
    }
    get metricChoices(): Array<{ text: string; value: ServiceMetricKey }> {
        if (!this.status) return []
        return Object.entries(this.status.metrics).map(([value, item]) => ({
            text: item.label,
            value: value as ServiceMetricKey,
        }))
    }
    get counterCards(): Array<{
        key: string
        label: string
        value: string
        note?: string
    }> {
        const c = this.status?.counters ?? {}
        return [
            {
                key: 'print',
                label: 'Print time',
                value: this.duration(c.print_time_s ?? 0),
            },
            {
                key: 'filament',
                label: 'Filament',
                value: this.distance(c.filament_mm ?? 0),
            },
            {
                key: 'prints',
                label: 'Prints started',
                value: Math.floor(c.prints ?? 0).toLocaleString(),
            },
            {
                key: 'xy',
                label: 'XY travel',
                value: this.distance(c.xy_distance_mm ?? 0),
                note: 'commanded',
            },
            {
                key: 'z',
                label: 'Z travel',
                value: this.distance(c.z_distance_mm ?? 0),
                note: 'commanded',
            },
            {
                key: 'hotend',
                label: 'Hotend heater',
                value: this.duration(c.hotend_heater_s ?? 0),
            },
            {
                key: 'bed',
                label: 'Bed heater',
                value: this.duration(c.bed_heater_s ?? 0),
            },
            {
                key: 'probe',
                label: 'Probe touches',
                value: Math.floor(c.probe_cycles ?? 0).toLocaleString(),
            },
        ]
    }

    emptyDraft(): TaskDraft {
        return {
            id: '',
            name: '',
            area: 'Custom',
            instructions: '',
            recommended: false,
            thresholds: [{ metric: 'print_time_s', value: 200 }],
        }
    }
    async refresh(): Promise<void> {
        if (!this.socketIsConnected) return
        this.loading = true
        try {
            this.status = await this.$socket.emitAndWait('machine.klippertools.service.status', {})
        } catch (error) {
            this.pageError = this.errorMessage(error)
        } finally {
            this.loading = false
        }
    }
    async action(payload: Record<string, unknown>): Promise<void> {
        this.status = await this.$socket.emitAndWait('machine.klippertools.service.action', payload)
    }
    editTask(task?: ServiceTask): void {
        this.editError = ''
        this.draft = task
            ? {
                  id: task.id,
                  name: task.name,
                  area: task.area,
                  instructions: task.instructions,
                  recommended: task.recommended,
                  thresholds: task.thresholds.map((item) => ({
                      metric: item.metric,
                      value: this.toDisplayLimit(item.metric, item.limit),
                  })),
              }
            : this.emptyDraft()
        this.showEditDialog = true
    }
    addThreshold(): void {
        this.draft.thresholds.push({ metric: 'calendar_s', value: 90 })
    }
    async saveDraft(): Promise<void> {
        this.editError = ''
        if (
            !this.draft.name.trim() ||
            !this.draft.thresholds.length ||
            this.draft.thresholds.some((item) => !(item.value > 0))
        ) {
            this.editError = 'Enter a name and at least one positive countdown.'
            return
        }
        try {
            await this.action({
                action: 'save_task',
                task: {
                    id: this.draft.id,
                    name: this.draft.name,
                    area: this.draft.area,
                    instructions: this.draft.instructions,
                    recommended: this.draft.recommended,
                    enabled: true,
                    thresholds: this.draft.thresholds.map((item) => ({
                        metric: item.metric,
                        limit: this.fromDisplayLimit(item.metric, item.value),
                        enabled: true,
                    })),
                },
            })
            this.showEditDialog = false
        } catch (error) {
            this.editError = this.errorMessage(error)
        }
    }
    async deleteDraft(): Promise<void> {
        await this.action({ action: 'delete_task', task_id: this.draft.id })
        this.showEditDialog = false
    }
    async markServiced(task: ServiceTask): Promise<void> {
        await this.action({ action: 'service_task', task_id: task.id })
    }
    async snooze(task: ServiceTask, mode: string): Promise<void> {
        await this.action({ action: 'snooze', task_id: task.id, mode })
    }
    async resetRecommended(): Promise<void> {
        await this.action({ action: 'reset_recommended' })
        this.showRecommendedReset = false
    }
    async resetCounters(): Promise<void> {
        await this.action({
            action: 'reset_counters',
            confirmation: this.resetConfirmation,
        })
        this.resetConfirmation = ''
        this.showCounterReset = false
    }
    async exportData(): Promise<void> {
        const payload = await this.$socket.emitAndWait('machine.klippertools.service.export', {})
        const url = URL.createObjectURL(
            new Blob([JSON.stringify(payload, null, 2)], {
                type: 'application/json',
            })
        )
        const link = document.createElement('a')
        link.href = url
        link.download = `klippertools-service-${new Date().toISOString().slice(0, 10)}.json`
        link.click()
        URL.revokeObjectURL(url)
    }
    importData(event: Event): void {
        const input = event.target as HTMLInputElement
        const file = input.files?.[0]
        if (!file) return
        const reader = new FileReader()
        reader.onload = async () => {
            try {
                await this.action({
                    action: 'import',
                    payload: JSON.parse(String(reader.result)),
                    replace: false,
                })
            } catch (error) {
                this.pageError = `Import failed: ${this.errorMessage(error)}`
            }
            input.value = ''
        }
        reader.readAsText(file)
    }
    taskColor(task: ServiceTask): string {
        return task.state === 'due' ? 'error' : task.state === 'soon' ? 'warning' : 'success'
    }
    duration(seconds: number): string {
        const days = Math.floor(seconds / 86400)
        const hours = Math.floor((seconds % 86400) / 3600)
        return days ? `${days}d ${hours}h` : `${hours}h ${Math.floor((seconds % 3600) / 60)}m`
    }
    distance(mm: number): string {
        const metres = mm / 1000
        return metres >= 10000 ? `${(metres / 1000).toFixed(1)} km` : `${metres.toFixed(metres >= 100 ? 0 : 1)} m`
    }
    remaining(metric: ServiceMetricStatus): string {
        const absolute = Math.abs(metric.remaining)
        const value =
            metric.unit === 'seconds'
                ? this.duration(absolute)
                : metric.unit === 'millimetres'
                  ? this.distance(absolute)
                  : `${Math.ceil(absolute)} ${metric.unit}`
        return metric.remaining < 0 ? `${value} overdue` : `${value} remaining`
    }
    dateTime(epoch: number): string {
        return new Date(epoch * 1000).toLocaleString()
    }
    historyTitle(entry: ServiceHistoryEntry): string {
        return entry.type === 'serviced'
            ? `${entry.task_name ?? 'Task'} marked serviced`
            : entry.type === 'recommended_reset'
              ? 'Recommended schedule restored'
              : entry.type === 'counters_reset'
                ? 'Lifetime counters reset'
                : entry.type === 'import'
                  ? 'Schedule imported'
                  : entry.type
    }
    displayUnit(metric: ServiceMetricKey): string {
        return metric === 'calendar_s'
            ? 'days'
            : metric.endsWith('_s')
              ? 'hours'
              : metric.includes('_mm')
                ? 'metres'
                : metric === 'probe_cycles'
                  ? 'touches'
                  : 'prints'
    }
    toDisplayLimit(metric: ServiceMetricKey, value: number): number {
        return metric === 'calendar_s'
            ? value / 86400
            : metric.endsWith('_s')
              ? value / 3600
              : metric.includes('_mm')
                ? value / 1000
                : value
    }
    fromDisplayLimit(metric: ServiceMetricKey, value: number): number {
        return metric === 'calendar_s'
            ? value * 86400
            : metric.endsWith('_s')
              ? value * 3600
              : metric.includes('_mm')
                ? value * 1000
                : value
    }
    defaultDisplayValue(metric: ServiceMetricKey): number {
        return metric === 'calendar_s'
            ? 90
            : metric.endsWith('_s')
              ? 200
              : metric.includes('_mm')
                ? 10000
                : metric === 'probe_cycles'
                  ? 10000
                  : 50
    }
    errorMessage(error: unknown): string {
        return typeof error === 'object' && error !== null && 'message' in error
            ? String((error as { message: unknown }).message)
            : String(error)
    }
}
</script>

<style scoped>
.service-manager {
    max-width: 1500px;
}
.h-100 {
    height: 100%;
}
.counter-card {
    border-top: 3px solid rgba(33, 150, 243, 0.55) !important;
}
.thermal-soak-card {
    border-top: 3px solid rgba(255, 152, 0, 0.62) !important;
}
.task-card {
    border-left-width: 5px !important;
}
.task-card--good {
    border-left-color: var(--v-success-base) !important;
}
.task-card--soon {
    border-left-color: var(--v-warning-base) !important;
}
.task-card--due {
    border-left-color: var(--v-error-base) !important;
}
.metric-grid {
    display: grid;
    gap: 6px;
}
.metric-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 7px 9px;
    border-radius: 6px;
    background: rgba(127, 127, 127, 0.07);
    font-size: 0.8rem;
}
.metric-row--due {
    background: rgba(244, 67, 54, 0.1);
    color: var(--v-error-base);
}
.instructions ::v-deep .v-expansion-panel-content__wrap {
    padding: 0 0 12px;
}
.threshold-row {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) minmax(150px, 0.65fr) 42px;
    gap: 9px;
    align-items: center;
    margin-bottom: 10px;
}
.danger-zone {
    border-color: rgba(244, 67, 54, 0.45) !important;
}
@media (max-width: 600px) {
    .threshold-row {
        grid-template-columns: 1fr 1fr 40px;
    }
}
</style>
