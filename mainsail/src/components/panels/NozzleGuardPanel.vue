<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiShieldCheckOutline"
        :title="$t('Panels.KlippertoolsPanel.Tabs.Guard')"
        :collapsible="true"
        card-class="nozzle-guard-panel"
        :hide-buttons-on-collapse="true">
        <nozzle-guard-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import NozzleGuardTool from '@/components/klippertools/NozzleGuardTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiShieldCheckOutline } from '@mdi/js'

@Component({ components: { NozzleGuardTool, Panel } })
export default class NozzleGuardPanel extends Mixins(BaseMixin) {
    mdiShieldCheckOutline = mdiShieldCheckOutline

    get available(): boolean {
        return Boolean(this.$store.state.printer?.nozzle_guard)
    }
}
</script>
