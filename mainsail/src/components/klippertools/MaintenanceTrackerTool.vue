<template>
  <div class="pa-4">
    <div class="d-flex align-center justify-space-between mb-3">
      <div>
        <div class="font-weight-medium">Next service</div>
        <div class="text-caption text--secondary">
          The first countdown to reach zero makes a task due.
        </div>
      </div>
      <v-btn small text color="primary" to="/klippertools">
        <v-icon small left>{{ mdiCogOutline }}</v-icon>
        Manage
      </v-btn>
    </div>

    <v-progress-linear
      v-if="loading && !status"
      indeterminate
      color="primary"
    />
    <v-list v-else-if="tasks.length" dense class="transparent pa-0">
      <v-list-item
        v-for="task in tasks.slice(0, 4)"
        :key="task.id"
        class="service-entry px-3"
        :class="`service-entry--${task.state}`"
        @click="openTask(task)"
      >
        <v-list-item-content>
          <div class="d-flex justify-space-between align-center mb-1">
            <v-list-item-title>{{ task.name }}</v-list-item-title>
            <v-chip x-small outlined :color="taskColor(task)">{{
              taskLabel(task)
            }}</v-chip>
          </div>
          <v-progress-linear
            :value="progress(task)"
            :color="taskColor(task)"
            height="7"
            rounded
          />
          <div class="countdowns mt-2">
            <span
              v-for="metric in task.metrics"
              :key="metric.metric"
              :class="{ 'error--text': metric.due }"
            >
              {{ metric.label }}: {{ remaining(metric) }}
            </span>
          </div>
          <div
            v-if="task.estimated_due"
            class="text-caption text--secondary mt-1"
          >
            Estimated due {{ dateTime(task.estimated_due) }}
          </div>
        </v-list-item-content>
        <v-list-item-icon class="ml-3 mr-0"
          ><v-icon small>{{ mdiChevronRight }}</v-icon></v-list-item-icon
        >
      </v-list-item>
    </v-list>
    <v-alert v-else dense text type="info" class="mb-0"
      >No service tasks are enabled.</v-alert
    >

    <v-dialog v-model="showTaskDialog" max-width="620">
      <v-card v-if="selectedTask">
        <v-card-title class="d-flex align-center">
          <v-icon :color="taskColor(selectedTask)" class="mr-3">{{
            mdiWrenchClock
          }}</v-icon>
          <span>{{ selectedTask.name }}</span>
        </v-card-title>
        <v-card-text>
          <v-alert v-if="selectedTask.due" dense text type="warning"
            >This service is due. The printer is not blocked.</v-alert
          >
          <p>{{ selectedTask.instructions }}</p>
          <v-list dense class="transparent">
            <v-list-item
              v-for="metric in selectedTask.metrics"
              :key="metric.metric"
              class="px-0"
            >
              <v-list-item-content>
                <v-list-item-title>{{ metric.label }}</v-list-item-title>
                <v-list-item-subtitle>{{
                  remaining(metric)
                }}</v-list-item-subtitle>
              </v-list-item-content>
              <v-list-item-action-text :class="metric.due ? 'error--text' : ''"
                >{{
                  Math.round(metric.progress * 100)
                }}%</v-list-item-action-text
              >
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions class="flex-wrap">
          <v-btn text small @click="runAction('snooze', { mode: 'next_print' })"
            >Snooze next print</v-btn
          >
          <v-btn text small @click="runAction('snooze', { mode: '24h' })"
            >Snooze 24h</v-btn
          >
          <v-spacer />
          <v-btn text @click="showTaskDialog = false">Close</v-btn>
          <v-btn color="success" text @click="runAction('service_task')"
            >Mark serviced</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import { Component, Mixins } from "vue-property-decorator";
import BaseMixin from "@/components/mixins/base";
import {
  ServiceManagerStatus,
  ServiceMetricStatus,
  ServiceTask,
} from "@/components/klippertools/types";
import { mdiChevronRight, mdiCogOutline, mdiWrenchClock } from "@mdi/js";

@Component
export default class MaintenanceTrackerTool extends Mixins(BaseMixin) {
  mdiChevronRight = mdiChevronRight;
  mdiCogOutline = mdiCogOutline;
  mdiWrenchClock = mdiWrenchClock;
  status: ServiceManagerStatus | null = null;
  loading = false;
  timer: number | null = null;
  selectedTask: ServiceTask | null = null;
  showTaskDialog = false;

  mounted(): void {
    this.refresh();
    this.timer = window.setInterval(() => this.refresh(), 5000);
  }

  beforeDestroy(): void {
    if (this.timer !== null) window.clearInterval(this.timer);
  }

  get tasks(): ServiceTask[] {
    return this.status?.tasks ?? [];
  }

  async refresh(): Promise<void> {
    if (
      !this.socketIsConnected ||
      !this.moonrakerComponents.includes("klippertools")
    )
      return;
    this.loading = true;
    try {
      this.status = await this.$socket.emitAndWait(
        "machine.klippertools.service.status",
        {},
      );
      this.$emit(
        "due-count",
        this.status?.tasks.filter((task) => task.due).length ?? 0,
      );
      if (this.selectedTask)
        this.selectedTask =
          this.tasks.find((task) => task.id === this.selectedTask?.id) ?? null;
      this.openReminderIfNeeded();
    } catch (error) {
      window.console.warn("Unable to load Klippertools Service Manager", error);
    } finally {
      this.loading = false;
    }
  }

  openReminderIfNeeded(): void {
    if (this.printerIsPrinting) return;
    const task = this.status?.notifications?.[0];
    if (!task || this.showTaskDialog) return;
    const signature = `${task.id}:${task.serviced_at}:${Math.floor(this.status?.counters.prints ?? 0)}`;
    const key = "klippertools-service-reminder";
    try {
      if (window.sessionStorage.getItem(key) === signature) return;
      window.sessionStorage.setItem(key, signature);
    } catch {
      // Private browsing may deny storage. The in-memory dialog guard remains safe.
    }
    this.openTask(task);
  }

  openTask(task: ServiceTask): void {
    this.selectedTask = task;
    this.showTaskDialog = true;
  }

  async runAction(
    action: string,
    extra: Record<string, unknown> = {},
  ): Promise<void> {
    if (!this.selectedTask) return;
    this.status = await this.$socket.emitAndWait(
      "machine.klippertools.service.action",
      {
        action,
        task_id: this.selectedTask.id,
        ...extra,
      },
    );
    this.showTaskDialog = false;
    this.selectedTask = null;
  }

  progress(task: ServiceTask): number {
    return Math.max(0, Math.min(100, task.progress * 100));
  }

  taskColor(task: ServiceTask): string {
    return task.state === "due"
      ? "error"
      : task.state === "soon"
        ? "warning"
        : "success";
  }

  taskLabel(task: ServiceTask): string {
    return task.state === "due"
      ? "Due"
      : task.state === "soon"
        ? "Soon"
        : "Good";
  }

  remaining(metric: ServiceMetricStatus): string {
    const value = metric.remaining;
    const prefix = value < 0 ? "" : "";
    const absolute = Math.abs(value);
    let text: string;
    if (metric.unit === "seconds") {
      const days = Math.floor(absolute / 86400);
      const hours = Math.floor((absolute % 86400) / 3600);
      const minutes = Math.floor((absolute % 3600) / 60);
      text = days ? `${days}d ${hours}h` : `${hours}h ${minutes}m`;
    } else if (metric.unit === "millimetres") {
      const metres = absolute / 1000;
      text =
        metres >= 10000
          ? `${(metres / 1000).toFixed(1)} km`
          : `${metres.toFixed(metres >= 100 ? 0 : 1)} m`;
    } else {
      text = `${Math.ceil(absolute)} ${metric.unit}`;
    }
    return value < 0 ? `${text} overdue` : `${prefix}${text} remaining`;
  }

  dateTime(value: number): string {
    return new Date(value * 1000).toLocaleDateString();
  }
}
</script>

<style scoped>
.service-entry {
  border: 1px solid rgba(127, 127, 127, 0.16);
  border-left-width: 4px;
  border-radius: 9px;
  cursor: pointer;
  margin-bottom: 8px;
  background: rgba(127, 127, 127, 0.045);
}
.service-entry--good {
  border-left-color: var(--v-success-base);
}
.service-entry--soon {
  border-left-color: var(--v-warning-base);
  background: rgba(255, 152, 0, 0.055);
}
.service-entry--due {
  border-left-color: var(--v-error-base);
  background: rgba(244, 67, 54, 0.065);
}
.countdowns {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 12px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.68);
}
</style>
