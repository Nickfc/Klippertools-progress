<template>
    <div class="tool-registry pa-4">
        <div class="d-flex flex-wrap align-center justify-space-between mb-3">
            <div>
                <div class="text-subtitle-1 font-weight-medium">Nozzle & Tool Registry</div>
                <div class="text-caption text--secondary">
                    Persistent profiles, install history, and usage tracking without rewriting printer.cfg.
                </div>
            </div>
            <div class="d-flex mt-2 mt-sm-0">
                <v-btn small outlined color="primary" class="mr-2" @click="editProfile()">
                    <v-icon small left>{{ mdiPlus }}</v-icon>
                    Add profile
                </v-btn>
                <v-btn small outlined @click="refresh">
                    <v-icon small left>{{ mdiRefresh }}</v-icon>
                    Refresh
                </v-btn>
            </div>
        </div>

        <v-alert v-if="error" dense text type="error" dismissible @input="error = ''">{{ error }}</v-alert>
        <v-progress-linear v-if="loading && !status" indeterminate color="primary" class="mb-3" />

        <template v-if="status">
            <v-alert
                dense
                text
                :type="status.sync.state === 'synchronized' ? 'success' : 'warning'"
                class="mb-3">
                {{ status.sync.message }}
                <span v-if="status.sync.error">· {{ status.sync.error }}</span>
            </v-alert>

            <v-card outlined class="mb-4">
                <v-card-title class="pb-2">
                    <div class="flex-grow-1">
                        <div class="text-subtitle-1">Installed tool</div>
                        <div class="text-caption text--secondary">
                            Nozzle Guard compares G-code against this profile while installed.
                        </div>
                    </div>
                    <v-chip small outlined :color="installed ? 'success' : 'warning'">
                        {{ installed ? 'Installed' : 'Unknown' }}
                    </v-chip>
                </v-card-title>
                <v-card-text v-if="installed">
                    <v-row dense>
                        <v-col cols="6" sm="3">
                            <div class="registry-value"><span>Name</span><strong>{{ installed.name }}</strong></div>
                        </v-col>
                        <v-col cols="6" sm="3">
                            <div class="registry-value"><span>Diameter</span><strong>{{ installed.diameter }} mm</strong></div>
                        </v-col>
                        <v-col cols="6" sm="3">
                            <div class="registry-value"><span>Material</span><strong>{{ installed.material }}</strong></div>
                        </v-col>
                        <v-col cols="6" sm="3">
                            <div class="registry-value">
                                <span>Installed</span><strong>{{ dateTime(installed.installed_at) }}</strong>
                            </div>
                        </v-col>
                    </v-row>
                    <div class="d-flex flex-wrap mt-3">
                        <v-chip small outlined class="mr-2 mb-2">
                            {{ distance(installed.usage_total.filament_mm) }} filament
                        </v-chip>
                        <v-chip small outlined class="mr-2 mb-2">
                            {{ duration(installed.usage_total.print_time_s) }} print time
                        </v-chip>
                        <v-chip small outlined class="mr-2 mb-2">
                            {{ Math.floor(installed.usage_total.prints) }} prints
                        </v-chip>
                    </div>
                </v-card-text>
                <v-card-text v-else class="text--secondary">
                    No installed profile is recorded. Nozzle Guard remains on Klipper's configured nozzle diameter.
                </v-card-text>
                <v-card-actions v-if="installed">
                    <v-spacer />
                    <v-btn small text color="warning" :disabled="printerIsPrinting" @click="clearInstalled">
                        Remove installed profile
                    </v-btn>
                </v-card-actions>
            </v-card>

            <v-row dense>
                <v-col v-for="profile in status.profiles" :key="profile.id" cols="12" md="6" xl="4">
                    <v-card outlined class="profile-card h-100" :class="{ 'profile-card--retired': profile.retired }">
                        <v-card-title class="pb-2">
                            <div class="flex-grow-1 min-width-0">
                                <div class="text-subtitle-1 text-truncate">{{ profile.name }}</div>
                                <div class="text-caption text--secondary">
                                    {{ profile.diameter }} mm · {{ profile.material }}
                                    <span v-if="profile.max_temp">· max {{ profile.max_temp }} °C</span>
                                </div>
                            </div>
                            <v-chip small outlined :color="profileColor(profile)">{{ profile.status }}</v-chip>
                        </v-card-title>
                        <v-card-text>
                            <div v-if="profile.notes" class="profile-notes mb-3">{{ profile.notes }}</div>
                            <div class="usage-grid">
                                <div><span>Filament</span><strong>{{ distance(profile.usage_total.filament_mm) }}</strong></div>
                                <div><span>Print time</span><strong>{{ duration(profile.usage_total.print_time_s) }}</strong></div>
                                <div><span>Prints</span><strong>{{ Math.floor(profile.usage_total.prints) }}</strong></div>
                                <div><span>Heater time</span><strong>{{ duration(profile.usage_total.hotend_heater_s) }}</strong></div>
                            </div>
                        </v-card-text>
                        <v-card-actions>
                            <v-btn small text @click="editProfile(profile)">
                                <v-icon small left>{{ mdiPencilOutline }}</v-icon>
                                Edit
                            </v-btn>
                            <v-btn
                                v-if="!profile.installed && !profile.retired"
                                small
                                text
                                color="success"
                                :disabled="printerIsPrinting"
                                @click="installProfile(profile)">
                                Install
                            </v-btn>
                            <v-spacer />
                            <v-menu offset-y>
                                <template #activator="{ on, attrs }">
                                    <v-btn icon small v-bind="attrs" v-on="on"><v-icon small>{{ mdiDotsVertical }}</v-icon></v-btn>
                                </template>
                                <v-list dense>
                                    <v-list-item v-if="!profile.installed && !profile.retired" @click="retireProfile(profile)">
                                        <v-list-item-title>Retire profile</v-list-item-title>
                                    </v-list-item>
                                    <v-list-item v-if="profile.retired" @click="restoreProfile(profile)">
                                        <v-list-item-title>Restore profile</v-list-item-title>
                                    </v-list-item>
                                    <v-list-item v-if="!profile.installed" @click="requestDelete(profile)">
                                        <v-list-item-title class="error--text">Delete profile</v-list-item-title>
                                    </v-list-item>
                                </v-list>
                            </v-menu>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>

            <div class="d-flex flex-wrap mt-4">
                <v-btn small text color="primary" @click="exportData">Export JSON</v-btn>
                <v-btn small text color="primary" @click="$refs.importInput.click()">Import JSON</v-btn>
                <input ref="importInput" type="file" accept="application/json,.json" hidden @change="importData" />
            </div>
        </template>

        <v-dialog v-model="showEdit" max-width="620" persistent>
            <v-card>
                <v-card-title>{{ draftExisting ? 'Edit tool profile' : 'Add tool profile' }}</v-card-title>
                <v-card-text>
                    <v-text-field v-model="draft.name" label="Name" outlined dense />
                    <v-row dense>
                        <v-col cols="12" sm="6">
                            <v-text-field
                                v-model.number="draft.diameter"
                                type="number"
                                min="0.05"
                                max="5"
                                step="0.05"
                                label="Nozzle diameter"
                                suffix="mm"
                                outlined
                                dense />
                        </v-col>
                        <v-col cols="12" sm="6">
                            <v-text-field v-model="draft.material" label="Tool material" outlined dense />
                        </v-col>
                    </v-row>
                    <v-text-field
                        v-model.number="draft.max_temp"
                        type="number"
                        min="1"
                        max="600"
                        label="Optional maximum temperature"
                        suffix="°C"
                        outlined
                        dense />
                    <v-textarea v-model="draft.notes" label="Notes" rows="3" outlined />
                    <v-alert dense text type="info" class="mb-0">
                        Saving an installed profile updates the in-memory comparison only. It never edits
                        <code>[extruder] nozzle_diameter</code>.
                    </v-alert>
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showEdit = false">Cancel</v-btn>
                    <v-btn text color="primary" :loading="saving" @click="saveProfile">Save</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="showDelete" max-width="520">
            <v-card>
                <v-card-title class="error--text">Delete tool profile?</v-card-title>
                <v-card-text>
                    The profile and its accumulated usage will be deleted. Type
                    <strong>DELETE TOOL PROFILE</strong> to continue.
                    <v-text-field v-model="deleteConfirmation" outlined dense class="mt-3" />
                </v-card-text>
                <v-card-actions>
                    <v-spacer />
                    <v-btn text @click="showDelete = false">Cancel</v-btn>
                    <v-btn
                        text
                        color="error"
                        :disabled="deleteConfirmation !== 'DELETE TOOL PROFILE'"
                        @click="deleteProfile">
                        Delete
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import { ToolProfile, ToolRegistryStatus } from '@/components/klippertools/types'
import { mdiDotsVertical, mdiPencilOutline, mdiPlus, mdiRefresh } from '@mdi/js'

interface ToolDraft {
    id: string
    name: string
    diameter: number | null
    material: string
    notes: string
    max_temp: number | null
}

@Component
export default class ToolRegistryTool extends Mixins(BaseMixin) {
    mdiDotsVertical = mdiDotsVertical
    mdiPencilOutline = mdiPencilOutline
    mdiPlus = mdiPlus
    mdiRefresh = mdiRefresh

    status: ToolRegistryStatus | null = null
    loading = false
    saving = false
    error = ''
    timer: number | null = null
    showEdit = false
    showDelete = false
    draftExisting = false
    deleteTarget: ToolProfile | null = null
    deleteConfirmation = ''
    draft: ToolDraft = this.emptyDraft()

    mounted(): void {
        this.refresh()
        this.timer = window.setInterval(() => this.refresh(), 5000)
    }

    beforeDestroy(): void {
        if (this.timer !== null) window.clearInterval(this.timer)
    }

    get installed(): ToolProfile | null {
        return this.status?.profiles.find((profile) => profile.installed) ?? null
    }

    emptyDraft(): ToolDraft {
        return { id: '', name: '', diameter: null, material: 'brass', notes: '', max_temp: null }
    }

    async refresh(): Promise<void> {
        if (!this.socketIsConnected || !this.moonrakerComponents.includes('klippertools')) return
        this.loading = true
        try {
            this.status = await this.$socket.emitAndWait('machine.klippertools.tools.status', {})
        } catch (error) {
            this.error = this.errorMessage(error)
        } finally {
            this.loading = false
        }
    }

    editProfile(profile?: ToolProfile): void {
        this.draftExisting = Boolean(profile)
        this.draft = profile
            ? {
                  id: profile.id,
                  name: profile.name,
                  diameter: profile.diameter,
                  material: profile.material,
                  notes: profile.notes,
                  max_temp: profile.max_temp,
              }
            : this.emptyDraft()
        this.showEdit = true
    }

    async saveProfile(): Promise<void> {
        if (!this.draft.name.trim() || !this.draft.diameter) {
            this.error = 'Name and nozzle diameter are required.'
            return
        }
        this.saving = true
        try {
            await this.action('save_profile', { profile: this.draft })
            this.showEdit = false
        } finally {
            this.saving = false
        }
    }

    async installProfile(profile: ToolProfile): Promise<void> {
        await this.action('install_profile', { profile_id: profile.id })
    }

    async clearInstalled(): Promise<void> {
        await this.action('clear_installed')
    }

    async retireProfile(profile: ToolProfile): Promise<void> {
        await this.action('retire_profile', { profile_id: profile.id })
    }

    async restoreProfile(profile: ToolProfile): Promise<void> {
        await this.action('restore_profile', { profile_id: profile.id })
    }

    requestDelete(profile: ToolProfile): void {
        this.deleteTarget = profile
        this.deleteConfirmation = ''
        this.showDelete = true
    }

    async deleteProfile(): Promise<void> {
        if (!this.deleteTarget) return
        await this.action('delete_profile', {
            profile_id: this.deleteTarget.id,
            confirmation: this.deleteConfirmation,
        })
        this.showDelete = false
        this.deleteTarget = null
    }

    async action(action: string, payload: Record<string, unknown> = {}): Promise<void> {
        try {
            this.status = await this.$socket.emitAndWait('machine.klippertools.tools.action', {
                action,
                ...payload,
            })
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    async exportData(): Promise<void> {
        try {
            const payload = await this.$socket.emitAndWait('machine.klippertools.tools.export', {})
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
            const link = document.createElement('a')
            link.href = URL.createObjectURL(blob)
            link.download = `klippertools-tools-${new Date().toISOString().slice(0, 10)}.json`
            link.click()
            URL.revokeObjectURL(link.href)
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    async importData(event: Event): Promise<void> {
        const input = event.target as HTMLInputElement
        const file = input.files?.[0]
        input.value = ''
        if (!file) return
        try {
            const payload = JSON.parse(await file.text())
            await this.action('import', { payload })
        } catch (error) {
            this.error = this.errorMessage(error)
        }
    }

    profileColor(profile: ToolProfile): string {
        if (profile.installed) return 'success'
        if (profile.retired) return 'grey'
        return 'primary'
    }

    duration(seconds: number): string {
        const hours = seconds / 3600
        return hours >= 10 ? `${Math.round(hours)} h` : `${hours.toFixed(1)} h`
    }

    distance(mm: number): string {
        const metres = mm / 1000
        return metres >= 1000 ? `${(metres / 1000).toFixed(1)} km` : `${metres.toFixed(1)} m`
    }

    dateTime(value: number | null): string {
        return value ? new Date(value * 1000).toLocaleString() : '—'
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
.min-width-0 {
    min-width: 0;
}

.profile-card--retired {
    opacity: 0.72;
}

.profile-notes {
    white-space: pre-wrap;
}

.registry-value,
.usage-grid > div {
    border: 1px solid rgba(127, 127, 127, 0.16);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 10px;
}

.registry-value span,
.usage-grid span {
    color: rgba(127, 127, 127, 0.9);
    font-size: 0.72rem;
}

.usage-grid {
    display: grid;
    gap: 8px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
}
</style>
