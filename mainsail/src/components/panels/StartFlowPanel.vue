<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiProgressClock"
        :title="$t('Panels.KlippertoolsPanel.Tabs.Start')"
        :collapsible="true"
        card-class="start-flow-panel"
        :hide-buttons-on-collapse="true">
        <start-flow-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import Panel from '@/components/ui/Panel.vue'
import StartFlowTool from '@/components/klippertools/StartFlowTool.vue'
import { mdiProgressClock } from '@mdi/js'

@Component({ components: { Panel, StartFlowTool } })
export default class StartFlowPanel extends Mixins(BaseMixin) {
    mdiProgressClock = mdiProgressClock

    get available(): boolean {
        return Boolean(this.$store.state.printer?.start_flow)
    }
}
</script>
