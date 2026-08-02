<template>
  <panel
    v-if="socketIsConnected && klipperState !== 'disconnected' && available"
    :icon="mdiWrenchClock"
    :title="$t('Panels.KlippertoolsPanel.Tabs.Maintenance')"
    :collapsible="true"
    card-class="maintenance-tracker-panel"
    :hide-buttons-on-collapse="true"
  >
    <template #buttons-title>
      <v-chip v-if="overdueCount" x-small color="error" outlined class="ml-2">
        {{ overdueCount }}
      </v-chip>
    </template>
    <maintenance-tracker-tool @due-count="overdueCount = $event" />
  </panel>
</template>

<script lang="ts">
import { Component, Mixins } from "vue-property-decorator";
import BaseMixin from "@/components/mixins/base";
import MaintenanceTrackerTool from "@/components/klippertools/MaintenanceTrackerTool.vue";
import Panel from "@/components/ui/Panel.vue";
import { mdiWrenchClock } from "@mdi/js";

@Component({ components: { MaintenanceTrackerTool, Panel } })
export default class MaintenanceTrackerPanel extends Mixins(BaseMixin) {
  mdiWrenchClock = mdiWrenchClock;
  overdueCount = 0;

  get available(): boolean {
    return this.moonrakerComponents.includes("klippertools");
  }
}
</script>
