<template>
    <panel
        v-if="socketIsConnected && klipperState !== 'disconnected' && available"
        :icon="mdiThermometerLines"
        title="Thermal Soak"
        :collapsible="true"
        card-class="thermal-soak-panel"
        :hide-buttons-on-collapse="true">
        <template #buttons-title>
            <v-chip
                v-if="status && status.active"
                x-small
                :color="status.state === 'stabilizing' ? 'warning' : 'primary'"
                outlined
                class="ml-2">
                {{ Math.round(status.progress) }}%
            </v-chip>
        </template>
        <thermal-soak-tool />
    </panel>
</template>

<script lang="ts">
import { Component, Mixins } from 'vue-property-decorator'
import BaseMixin from '@/components/mixins/base'
import ThermalSoakTool from '@/components/klippertools/ThermalSoakTool.vue'
import Panel from '@/components/ui/Panel.vue'
import { mdiThermometerLines } from '@mdi/js'
import { ThermalSoakStatus } from '@/components/klippertools/types'

@Component({ components: { ThermalSoakTool, Panel } })
export default class ThermalSoakPanel extends Mixins(BaseMixin) {
    mdiThermometerLines = mdiThermometerLines

    get status(): ThermalSoakStatus | null {
        return this.$store.state.printer?.thermal_soak ?? null
    }

    get available(): boolean {
        return Boolean(this.status?.ready)
    }
}
</script>
