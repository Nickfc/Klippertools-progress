<template>
    <div class="health-timeline pa-4">
        <div class="d-flex flex-wrap align-center justify-space-between mb-3">
            <div>
                <div class="text-subtitle-1 font-weight-medium">Printer Health Timeline</div>
                <div class="text-caption text--secondary">
                    Explainable facts from prints, calibrations, service actions, updates, and warnings.
                </div>
            </div>
            <div class="d-flex mt-2 mt-sm-0">
                <v-btn small outlined color="primary" class="mr-2" @click="exportData">
                    <v-icon small left>{{ mdiCloudDownloadOutline }}</v-icon>
                    Export JSON
                </v-btn>
                <v-btn small outlined @click="refresh">
                    <v-icon small left>{{ mdiRefresh }}</v-icon>
                    Refresh
                </v-btn>
            </div>
        </div>

        <v-alert dense text type="info" class="mb-3">
            Events show their source and recorded details. The timeline never stores G-code contents and does not infer
            a successful configuration save merely because Klipper's pending-change state disappeared.
        </v-alert>
        <v-alert v-if="error" dense text type="error" dismissible class="mb-3" @input="error = ''">
            {{ error }}
        </v-alert>
        <v-progress-linear v-if="loading && !status" indeterminate color="primary" class="mb-3" />

        <template v-if="status">
            <v-card outlined class="mb-3">
                <v-card-text>
                    <v-row dense align="center">
                        <v-col cols="12" sm="4" md="3">
                            <v-select
                                v-model="category"
                                :items="categoryItems"
                                label="Category"
                                outlined
                                dense
                                hide-details
                                @change="refresh" />
                        </v-col>
                        <v-col cols="12" sm="4" md="3">
                            <v-text-field
                                v-model.trim="eventType"
                                label="Exact event type"
                                placeholder="e.g. print_failed"
                                outlined
                                dense
                                clearable
                                hide-details
                                @keyup.enter="refresh" />
                        </v-col>
                        <v-col cols="6" sm="2" md="2">
                            <v-select
                                v-model="days"
                                :items="dayItems"
                                label="Period"
                                outlined
                                dense
                                hide-details
                                @change="refresh" />
                        </v-col>
                        <v-col cols="6" sm="2" md="2">
                            <v-select
                                v-model="limit"
                                :items="limitItems"
                                label="Limit"
                                outlined
                                dense
                                hide-details
                                @change="refresh" />
                        </v-col>
                        <v-col cols="12" md="2" class="text-md-right">
                            <v-chip small outlined>{{ status.total_events }} retained</v-chip>
                        </v-col>
                    </v-row>
                </v-card-text>
            </v-card>

            <v-timeline v-if="status.events.length" dense align-top class="timeline-list">
                <v-timeline-item
                    v-for="event in status.events"
                    :key="event.id"
                    :color="severityColor(event.severity)"
                    small>
                    <v-card outlined>
                        <v-card-title class="event-title py-2 px-3">
                            <div class="min-width-0 flex-grow-1">
                                <div class="text-subtitle-2">{{ event.summary }}</div>
                                <div class="text-caption text--secondary">
                                    {{ dateTime(event.at) }} · {{ event.category }} · {{ event.type }}
                                </div>
                            </div>
                            <v-chip x-small outlined :color="severityColor(event.severity)">
                                {{ event.severity }}
                            </v-chip>
                        </v-card-title>
                        <v-card-text class="pt-1 pb-2 px-3">
                            <div class="text-caption mb-2">
                                <strong>Source:</strong> <code>{{ event.source }}</code>
                            </div>
                            <v-expansion-panels v-if="hasDetails(event)" flat accordion>
                                <v-expansion-panel>
                                    <v-expansion-panel-header class="px-0 py-1 text-caption">
                                        Recorded details
                                    </v-expansion-panel-header>
                                    <v-expansion-panel-content class="event-details">
                                        <pre>{{ prettyDetails(event) }}</pre>
                                    </v-expansion-panel-content>
                                </v-expansion-panel>
                            </v-expansion-panels>
                        </v-card-text>
                    </v-card>
                </v-timeline-item>
            </v-timeline>
            <v-card v-else outlined>
                <v-card-text class="text--secondary">
                    No recorded events match the selected filters.
                </v-card-text>
            </v-card>

            <v-card outlined class="mt-4">
                <v-card-title class="text-subtitle-1">Retention</v-card-title>
                <v-card-text>
                    <v-row dense>
                        <v-col cols="12" sm="6">
                            <v-text-field
                                v-model.number="retentionDays"
                                type="number"
                                min="1"
                                max="3650"
                                label="Keep events for"
                                suffix="days"
                                outlined
                                dense />
                        </v-col>
                        <v-col cols="12" sm="6">
                            <v-text-field
                                v-model.number="eventLimit"
                                type="number"
                                min="100"
                                max="20000"
                                label="Maximum retained events"
                                outlined
                                dense />
                        </v-col>
                    </v-row>
                    <div class="text-caption text--secondary">
                        Whichever limit is reached first applies. Storage is atomic and remains local to the printer.
                    </div>
                </v-card-text>
                <v-card-actions>
                    <v-btn text color="primary" @click="saveRetention">Save retention</v-btn>
                    <v-spacer />
                    <v-btn text color="error" @click="openClear">Clear timeline</v-btn>
                </v-card-actions>
            </v-card>
        </template>

        <v-dialog v-model="showClear" max-width="560">
            <v-card>
                <v-card-title class="error--text">Clear Printer Health Timeline?</v-card-title>
                <v-card-text>
                    This removes the retained event history. Type <strong>CLEAR HEALTH TIMELINE</strong> to continue.
                    <v-text-field v-model="clearConfirmation" outlined dense class="mt-3" />
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showClear = false">Cancel</v-btn>
                    <v-btn
                        text
                        color="error"
                        :disabled="clearConfirmation !== 'CLEAR HEALTH TIMELINE'"
                        @click="clearTimeline">
                        Clear timeline
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { HealthTimelineEvent, HealthTimelineStatus } from '@/components/klippertools/types'
import { mdiCloudDownloadOutline, mdiRefresh } from '@mdi/js'

@Component
export default class HealthTimelineTool extends Mixins(BaseMixin) {
    mdiCloudDownloadOutline = mdiCloudDownloadOutline
    mdiRefresh = mdiRefresh

    status: HealthTimelineStatus | null = null
    loading = false
    error = ''
    timer: number | null = null
    category = ''
    eventType = ''
    days = 90
    limit = 300
    retentionDays = 365
    eventLimit = 2000
    showClear = false
    clearConfirmation = ''

    mounted(): void {
        this.refresh()
        this.timer = window.setInterval(() => this.refresh(), 10000)
    }

    beforeDestroy(): void {
        if (this.timer !== null) window.clearInterval(this.timer)
    }

    get categoryItems(): Array<{ text: string; value: string }> {
        const categories = this.status?.categories ?? []
        return [{ text: 'All categories', value: '' }].concat(
            categories.map((value) => ({ text: value, value }))
        )
    }

    get dayItems(): Array<{ text: string; value: number }> {
        return [
            { text: '24 hours', value: 1 },
            { text: '7 days', value: 7 },
            { text: '30 days', value: 30 },
            { text: '90 days', value: 90 },
            { text: '1 year', value: 365 },
            { text: 'All retained', value: 0 },
        ]
    }

    get limitItems(): number[] {
        return [100, 300, 500, 1000, 2000]
    }

    async refresh(): Promise<void> {
        if (!this.socketIsConnected || !this.moonrakerComponents.includes('klippertools')) return
        this.loading = true
        try {
            const payload: Record<string, unknown> = {
                category: this.category,
                type: this.eventType,
                limit: this.limit,
            }
            if (this.days > 0) payload.start_at = Date.now() / 1000 - this.days * 86400
            const firstLoad = this.status === null
            this.status = await this.$socket.emitAndWait('machine.klippertools.timeline.status', payload)
            if (firstLoad && this.status) {
                this.retentionDays = this.status.retention_days
                this.eventLimit = this.status.event_limit
            }
        } catch (error) {
            this.error = this.errorMessage(error)
        } finally {
            this.loading = false
        }
    }

    async saveRetention(): Promise<void> {
        try {
            this.status = await this.$socket.emitAndWait('machine.klippertools.timeline.action', {
                action: 'retention',
                retention_days: this.retentionDays,
                event_limit: this.eventLimit,
            })
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    openClear(): void {
        this.clearConfirmation = ''
        this.showClear = true
    }

    async clearTimeline(): Promise<void> {
        try {
            this.status = await this.$socket.emitAndWait('machine.klippertools.timeline.action', {
                action: 'clear',
                confirmation: this.clearConfirmation,
                limit: this.limit,
            })
            this.showClear = false
            this.clearConfirmation = ''
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    async exportData(): Promise<void> {
        try {
            const payload = await this.$socket.emitAndWait('machine.klippertools.timeline.export', {})
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
            const link = document.createElement('a')
            link.href = URL.createObjectURL(blob)
            link.download = `klippertools-health-timeline-${new Date().toISOString().slice(0, 10)}.json`
            link.click()
            URL.revokeObjectURL(link.href)
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    severityColor(severity: string): string {
        return severity === 'error' ? 'error' : severity === 'warning' ? 'warning' : 'primary'
    }

    hasDetails(event: HealthTimelineEvent): boolean {
        return Object.keys(event.details ?? {}).length > 0
    }

    prettyDetails(event: HealthTimelineEvent): string {
        return JSON.stringify(event.details ?? {}, null, 2)
    }

    dateTime(epoch: number): string {
        return new Date(epoch * 1000).toLocaleString()
    }

    errorMessage(error: unknown): string {
        if (typeof error === 'object' && error !== null && 'message' in error) {
            return String((error as { message: unknown }).message)
        }
        return String(error)
    }
}
</script>

<style scoped>
.health-timeline {
    max-width: 1500px;
}

.min-width-0 {
    min-width: 0;
}

.event-title {
    gap: 10px;
}

.event-details ::v-deep .v-expansion-panel-content__wrap {
    padding: 0 0 10px;
}

.event-details pre {
    background: rgba(127, 127, 127, 0.08);
    border-radius: 6px;
    font-size: 0.72rem;
    margin: 0;
    max-height: 260px;
    overflow: auto;
    padding: 10px;
    white-space: pre-wrap;
    word-break: break-word;
}
</style>
