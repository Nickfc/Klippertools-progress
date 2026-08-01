<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiTuneVariant"
        :title="$t('Panels.KlippertoolsPanel.Tabs.Motion')"
        :collapsible="true"
        card-class="motion-wizard-panel"
        :hide-buttons-on-collapse="true">
        <motion-wizard-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import MotionWizardTool from '@/components/klippertools/MotionWizardTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiTuneVariant } from '@mdi/js'

@Component({ components: { MotionWizardTool, Panel } })
export default class MotionWizardPanel extends Mixins(BaseMixin) {
    mdiTuneVariant = mdiTuneVariant

    get available(): boolean {
        return Boolean(this.$store.state.printer?.motion_wizard)
    }
}
</script>
