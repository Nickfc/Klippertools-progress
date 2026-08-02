<template>
    <panel
        v-if="socketIsConnected && moonrakerComponents.includes('klippertools')"
        :icon="mdiHistory"
        title="Printer Health Timeline"
        :collapsible="true"
        card-class="health-timeline-panel"
        :hide-buttons-on-collapse="true">
        <health-timeline-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import HealthTimelineTool from '@/components/klippertools/HealthTimelineTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiHistory } from '@mdi/js'

@Component({ components: { HealthTimelineTool, Panel } })
export default class HealthTimelinePanel extends Mixins(BaseMixin) {
    mdiHistory = mdiHistory
}
</script>
