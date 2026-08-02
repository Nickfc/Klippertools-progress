<template>
    <panel
        v-if="socketIsConnected && moonrakerComponents.includes('klippertools')"
        :icon="mdiToolboxOutline"
        title="Nozzle & Tool Registry"
        :collapsible="true"
        card-class="tool-registry-panel"
        :hide-buttons-on-collapse="true">
        <tool-registry-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import ToolRegistryTool from '@/components/klippertools/ToolRegistryTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiToolboxOutline } from '@mdi/js'

@Component({ components: { Panel, ToolRegistryTool } })
export default class ToolRegistryPanel extends Mixins(BaseMixin) {
    mdiToolboxOutline = mdiToolboxOutline
}
</script>
