<template>
  <panel
    v-if="socketIsConnected && klipperState !== 'disconnected' && available"
    :icon="mdiToolboxOutline"
    :title="$t('Panels.KlippertoolsPanel.Headline')"
    :collapsible="true"
    card-class="klippertools-panel"
    :hide-buttons-on-collapse="true"
  >
    <template #buttons-title>
      <v-chip v-if="attentionCount" x-small color="error" outlined class="ml-2">
        {{
          $t("Panels.KlippertoolsPanel.Attention", { count: attentionCount })
        }}
      </v-chip>
    </template>

    <v-card-text class="klippertools-core">
      <div class="klippertools-core__identity">
        <div class="klippertools-core__mark">
          <v-icon color="primary">{{ mdiToolboxOutline }}</v-icon>
        </div>
        <div class="flex-grow-1">
          <div class="font-weight-medium">
            {{ $t("Panels.KlippertoolsPanel.Headline") }}
          </div>
          <div class="text-caption text--secondary">
            {{
              $t("Panels.KlippertoolsPanel.Update.Installed", {
                version: installedVersion,
              })
            }}
          </div>
        </div>
        <v-chip x-small outlined color="success"
          >{{ enabledToolCount }} / 4</v-chip
        >
      </div>

      <div class="klippertools-core__tools">
        <div
          v-for="tool in toolStatuses"
          :key="tool.key"
          class="klippertools-core__tool"
          :class="{ 'klippertools-core__tool--available': tool.available }"
        >
          <v-icon small>{{ tool.icon }}</v-icon>
          <span>{{ tool.label }}</span>
          <i />
        </div>
      </div>

      <v-btn
        v-if="updaterAvailable"
        block
        small
        outlined
        color="primary"
        :loading="updateStatus.updating"
        :disabled="printerIsPrinting"
        @click="openUpdateDialog"
      >
        <v-icon small left>{{ mdiCloudDownloadOutline }}</v-icon>
        {{ $t("Panels.KlippertoolsPanel.Update.Action") }}
      </v-btn>
    </v-card-text>

    <v-dialog v-model="showUpdateDialog" max-width="520">
      <v-card>
        <v-card-title>{{
          $t("Panels.KlippertoolsPanel.Update.Title")
        }}</v-card-title>
        <v-card-text>
          <v-alert v-if="printerIsPrinting" dense text type="warning">
            {{ $t("Panels.KlippertoolsPanel.Update.PrintingBlocked") }}
          </v-alert>
          <p>{{ $t("Panels.KlippertoolsPanel.Update.Description") }}</p>
          <div class="text-caption text--secondary">
            {{
              $t("Panels.KlippertoolsPanel.Update.Installed", {
                version: installedVersion,
              })
            }}
          </div>
          <v-progress-linear
            v-if="updateStatus.updating"
            indeterminate
            color="primary"
            class="mt-4"
          />
          <v-alert
            v-if="updateStatus.message"
            :type="
              updateStatus.state === 'error'
                ? 'error'
                : updateStatus.state === 'complete'
                  ? 'success'
                  : 'info'
            "
            dense
            text
            class="mt-4 mb-0"
          >
            {{ updateStatus.message }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn
            text
            :disabled="updateStatus.updating"
            @click="showUpdateDialog = false"
          >
            {{ $t("Buttons.Cancel") }}
          </v-btn>
          <v-btn
            color="primary"
            text
            :loading="updateStatus.updating"
            :disabled="printerIsPrinting || updateStatus.updating"
            @click="startUpdate"
          >
            {{ $t("Panels.KlippertoolsPanel.Update.Action") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </panel>
</template>

<script lang="ts">
import { Component, Mixins } from "vue-property-decorator";
import BaseMixin from "@/components/mixins/base";
import Panel from "@/components/ui/Panel.vue";
import {
  mdiCloudDownloadOutline,
  mdiProgressClock,
  mdiShieldCheckOutline,
  mdiToolboxOutline,
  mdiTuneVariant,
  mdiWrenchClock,
} from "@mdi/js";

interface UpdateStatus {
  state: string;
  message: string;
  installed_version: string;
  updating: boolean;
  restart_required?: boolean;
}

interface ToolStatus {
  key: string;
  label: string;
  icon: string;
  available: boolean;
}

@Component({
  components: {
    Panel,
  },
})
export default class KlippertoolsPanel extends Mixins(BaseMixin) {
  mdiCloudDownloadOutline = mdiCloudDownloadOutline;
  mdiProgressClock = mdiProgressClock;
  mdiShieldCheckOutline = mdiShieldCheckOutline;
  mdiToolboxOutline = mdiToolboxOutline;
  mdiTuneVariant = mdiTuneVariant;
  mdiWrenchClock = mdiWrenchClock;

  showUpdateDialog = false;
  updateTimer: number | null = null;
  updateStatus: UpdateStatus = {
    state: "idle",
    message: "",
    installed_version: "unknown",
    updating: false,
  };

  mounted(): void {
    if (this.updaterAvailable) this.refreshUpdateStatus();
  }

  beforeDestroy(): void {
    this.stopUpdatePolling();
  }

  get available(): boolean {
    return Boolean(
      this.$store.state.printer?.nozzle_guard ||
      this.$store.state.printer?.start_flow ||
      this.$store.state.printer?.motion_wizard,
    );
  }

  get attentionCount(): number {
    const nozzleMismatch = this.$store.state.printer?.nozzle_guard?.blocking
      ? 1
      : 0;
    return nozzleMismatch;
  }

  get updaterAvailable(): boolean {
    return this.moonrakerComponents.includes("klippertools");
  }

  get installedVersion(): string {
    return this.updateStatus.installed_version || "unknown";
  }

  get toolStatuses(): ToolStatus[] {
    return [
      {
        key: "guard",
        label: String(this.$t("Panels.KlippertoolsPanel.Tabs.Guard")),
        icon: mdiShieldCheckOutline,
        available: Boolean(this.$store.state.printer?.nozzle_guard),
      },
      {
        key: "start",
        label: String(this.$t("Panels.KlippertoolsPanel.Tabs.Start")),
        icon: mdiProgressClock,
        available: Boolean(this.$store.state.printer?.start_flow),
      },
      {
        key: "maintenance",
        label: String(this.$t("Panels.KlippertoolsPanel.Tabs.Maintenance")),
        icon: mdiWrenchClock,
        available: this.moonrakerComponents.includes("klippertools"),
      },
      {
        key: "motion",
        label: String(this.$t("Panels.KlippertoolsPanel.Tabs.Motion")),
        icon: mdiTuneVariant,
        available: Boolean(this.$store.state.printer?.motion_wizard),
      },
    ];
  }

  get enabledToolCount(): number {
    return this.toolStatuses.filter((tool) => tool.available).length;
  }

  async openUpdateDialog(): Promise<void> {
    this.showUpdateDialog = true;
    await this.refreshUpdateStatus();
  }

  async refreshUpdateStatus(): Promise<void> {
    if (!this.updaterAvailable || !this.socketIsConnected) return;
    try {
      const status = await this.$socket.emitAndWait(
        "machine.klippertools.status",
        {},
      );
      this.updateStatus = { ...this.updateStatus, ...status };
      if (!this.updateStatus.updating) this.stopUpdatePolling();
    } catch (error) {
      this.updateStatus = {
        ...this.updateStatus,
        state: "error",
        message: this.errorMessage(error),
        updating: false,
      };
      this.stopUpdatePolling();
    }
  }

  async startUpdate(): Promise<void> {
    this.updateStatus = {
      ...this.updateStatus,
      state: "starting",
      message: String(this.$t("Panels.KlippertoolsPanel.Update.Starting")),
      updating: true,
    };
    try {
      await this.$socket.emitAndWait("machine.klippertools.update", {});
      this.startUpdatePolling();
    } catch (error) {
      this.updateStatus = {
        ...this.updateStatus,
        state: "error",
        message: this.errorMessage(error),
        updating: false,
      };
    }
  }

  startUpdatePolling(): void {
    this.stopUpdatePolling();
    this.updateTimer = window.setInterval(
      () => this.refreshUpdateStatus(),
      1500,
    );
  }

  stopUpdatePolling(): void {
    if (this.updateTimer !== null) window.clearInterval(this.updateTimer);
    this.updateTimer = null;
  }

  errorMessage(error: unknown): string {
    if (typeof error === "object" && error !== null && "message" in error) {
      return String((error as { message: unknown }).message);
    }
    return String(this.$t("Panels.KlippertoolsPanel.Update.Failed"));
  }
}
</script>

<style scoped>
.klippertools-core {
  padding: 14px 16px 16px;
}

.klippertools-core__identity {
  align-items: center;
  display: flex;
  gap: 11px;
  margin-bottom: 12px;
}

.klippertools-core__mark {
  align-items: center;
  border: 1px solid rgba(33, 150, 243, 0.28);
  border-radius: 9px;
  display: flex;
  height: 40px;
  justify-content: center;
  width: 40px;
  background: rgba(33, 150, 243, 0.09);
}

.klippertools-core__tools {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
  margin-bottom: 12px;
}

.klippertools-core__tool {
  align-items: center;
  border: 1px solid rgba(127, 127, 127, 0.14);
  border-radius: 7px;
  color: rgba(127, 127, 127, 0.82);
  display: grid;
  font-size: 0.72rem;
  gap: 7px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-width: 0;
  padding: 7px 8px;
  background: rgba(127, 127, 127, 0.035);
}

.klippertools-core__tool span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.klippertools-core__tool i {
  border-radius: 50%;
  height: 7px;
  width: 7px;
  background: rgba(127, 127, 127, 0.45);
}

.klippertools-core__tool--available {
  border-color: rgba(76, 175, 80, 0.22);
  color: inherit;
  background: rgba(76, 175, 80, 0.045);
}

.klippertools-core__tool--available i {
  background: #66bb6a;
}
</style>
