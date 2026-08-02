<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiTuneVariant"
        title="Calibration Center"
        :collapsible="true"
        card-class="calibration-center-panel"
        :hide-buttons-on-collapse="true">
        <template #buttons-title>
            <v-chip v-if="status && status.active" x-small color="warning" outlined class="ml-2">
                {{ status.phase }}
            </v-chip>
        </template>
        <calibration-center-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import CalibrationCenterTool from '@/components/klippertools/CalibrationCenterTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiTuneVariant } from '@mdi/js'
import { CalibrationCenterStatus } from '@/components/klippertools/types'

@Component({ components: { CalibrationCenterTool, Panel } })
export default class CalibrationCenterPanel extends Mixins(BaseMixin) {
    mdiTuneVariant = mdiTuneVariant

    get status(): CalibrationCenterStatus | null {
        return this.$store.state.printer?.calibration_center ?? null
    }

    get available(): boolean {
        return Boolean(this.status?.ready)
    }
}
</script>
