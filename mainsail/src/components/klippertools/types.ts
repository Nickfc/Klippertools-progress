export interface NozzleGuardStatus {
    version: string
    ready: boolean
    state: 'no_file' | 'disabled' | 'unknown' | 'match' | 'mismatch' | 'overridden' | 'error'
    message: string
    mode: 'block' | 'warn' | 'off'
    blocking: boolean
    filename: string | null
    configured_nozzle: number
    klipper_nozzle: number
    comparison_source: 'klipper' | 'registry'
    installed_profile_id: string | null
    installed_profile_name: string | null
    detected_nozzles: number[]
    tolerance: number
    metadata_source: string | null
    overridden: boolean
}

export interface StartFlowStage {
    name: string
    label: string
    state: 'pending' | 'active' | 'done' | 'error'
    duration_seconds: number | null
    estimate_seconds: number
}

export interface StartFlowStatus {
    version: string
    state: 'idle' | 'running' | 'complete' | 'error'
    active: boolean
    message: string
    error: string | null
    instrumentation_seen: boolean
    current_stage: string | null
    completed_stages: number
    total_stages: number
    progress: number
    eta_seconds: number | null
    elapsed_seconds: number
    stages: StartFlowStage[]
}

export interface MotionWizardResult {
    type: string
    frequency: number
    damping_ratio: number
    calibrated: boolean
}

export interface MotionWizardStatus {
    version: string
    ready: boolean
    state: 'idle' | 'ready' | 'running' | 'review' | 'error' | 'unavailable'
    phase: string
    active: boolean
    message: string
    error: string | null
    homed_axes: string
    noise_complete: boolean
    completed_axes: string[]
    pending_save: boolean
    progress: number
    elapsed_seconds: number
    results: Record<string, MotionWizardResult>
}


export interface CalibrationCenterFlow {
    title: string
    available: boolean
    reason: string | null
    command: string | null
    requires_homing: boolean
    attended: boolean
    heats: boolean
    moves: boolean
    permanent_result: boolean
}

export interface CalibrationCenterHeater {
    name: string
    min_temp: number | null
    max_temp: number | null
    temperature: number | null
    target: number | null
    control: string | null
}

export interface CalibrationCenterCurrentValues {
    pressure_advance: number | null
    rotation_distance: number | null
    probe_z_offset: number | null
    z_endstop_position: number | null
    input_shaper: Record<string, string | number | null>
    bed_mesh_profile: string | null
    manual_probe: Record<string, unknown>
    heaters: CalibrationCenterHeater[]
    save_config_pending: boolean
    save_config_pending_items: Record<string, unknown>
}

export interface CalibrationCenterStatus {
    version: string
    ready: boolean
    session_id: number
    state: 'idle' | 'running' | 'guided' | 'review' | 'error'
    phase: string
    active_flow: string | null
    active: boolean
    message: string
    error: string | null
    elapsed_seconds: number
    last_result: Record<string, unknown> | null
    last_command: string | null
    printer_state: string | null
    homed_axes: string
    flows: Record<string, CalibrationCenterFlow>
    current_values: CalibrationCenterCurrentValues
    automatic_save: false
}

export interface ThermalSoakDefaults {
    sensor: string
    window_seconds: number
    max_wait_seconds: number
    temperature_tolerance: number
    slope_limit_c_per_min: number
    range_limit_c: number
}

export interface ThermalSoakStatus {
    version: string
    ready: boolean
    session_id: number
    state: 'idle' | 'heating' | 'stabilizing' | 'stable' | 'timed_out' | 'canceled' | 'error'
    active: boolean
    message: string
    error: string | null
    sensor: string | null
    available_sensors: string[]
    target: number
    temperature: number | null
    sensor_target: number
    temperature_tolerance: number
    slope_limit_c_per_min: number
    slope_c_per_min: number | null
    range_limit_c: number
    range_c: number | null
    window_seconds: number
    max_wait_seconds: number
    stable_seconds: number
    elapsed_seconds: number
    eta_seconds: number | null
    learned_duration_seconds: number | null
    progress: number
    defaults: ThermalSoakDefaults
}

export type ServiceMetricKey =
    | 'print_time_s'
    | 'filament_mm'
    | 'prints'
    | 'calendar_s'
    | 'xy_distance_mm'
    | 'z_distance_mm'
    | 'hotend_heater_s'
    | 'bed_heater_s'
    | 'probe_cycles'

export interface ServiceThreshold {
    metric: ServiceMetricKey
    limit: number
    enabled: boolean
}

export interface ServiceMetricStatus extends ServiceThreshold {
    label: string
    unit: string
    used: number
    remaining: number
    progress: number
    due: boolean
    estimated_due: number | null
}

export interface ServiceTask {
    id: string
    name: string
    area: string
    instructions: string
    enabled: boolean
    recommended: boolean
    serviced_at: number
    baseline: Record<string, number>
    snoozed_until: number
    snooze_prints_until: number
    updated_at: number
    thresholds: ServiceThreshold[]
    metrics: ServiceMetricStatus[]
    base_progress: number
    progress: number
    base_state: 'good' | 'soon' | 'due'
    state: 'good' | 'soon' | 'due'
    base_due: boolean
    due: boolean
    snoozed: boolean
    estimated_due: number | null
    smart_signals: string[]
    smart: SmartMaintenanceTaskStatus
}

export interface SmartMaintenanceEvidence {
    id: string
    at: number
    type: string
    severity: 'warning' | 'error'
    summary: string
}

export interface SmartMaintenanceTaskStatus {
    enabled: boolean
    state: 'disabled' | 'insufficient_data' | 'suggestion'
    confidence: 'none' | 'low' | 'medium' | 'high'
    signals: string[]
    evidence_count: number
    weighted_score: number
    advance_fraction: number
    effective_progress: number
    smart_due: boolean
    reason: string
    limiting_threshold: ServiceMetricStatus | null
    evidence: SmartMaintenanceEvidence[]
}

export interface SmartMaintenanceSettings {
    enabled: boolean
    lookback_days: number
    min_events: number
    max_advance_fraction: number
    reset_at: number
}

export interface MechanismPreset {
    label: string
    focus: string[]
    note: string
}

export interface ServiceHistoryEntry {
    type: string
    at: number
    task_id?: string
    task_name?: string
    note?: string
}

export interface ServiceManagerStatus {
    schema: number
    printer_state: string
    counter_kind: Record<string, string>
    metrics: Record<ServiceMetricKey, { label: string; unit: string }>
    counters: Record<string, number>
    tasks: ServiceTask[]
    notifications: ServiceTask[]
    history: ServiceHistoryEntry[]
    recommended_count: number
    smart: SmartMaintenanceSettings
    mechanism: string
    mechanism_preset: MechanismPreset | null
    updated_at: number
}

export interface ToolUsage {
    print_time_s: number
    filament_mm: number
    prints: number
    hotend_heater_s: number
}

export interface ToolProfile {
    id: string
    name: string
    diameter: number
    material: string
    notes: string
    max_temp: number | null
    retired: boolean
    retired_at: number | null
    installed_at: number | null
    created_at: number
    updated_at: number
    installed: boolean
    status: 'installed' | 'available' | 'retired'
    usage_total: ToolUsage
}

export interface ToolHistoryEntry {
    type: string
    at: number
    profile_id: string
    profile_name: string
    details?: Record<string, unknown>
}

export interface ToolRegistryStatus {
    schema: number
    installed_profile_id: string | null
    profiles: ToolProfile[]
    history: ToolHistoryEntry[]
    sync: { state: string; message: string; error?: string | null }
    updated_at: number
}

export interface HealthTimelineEvent {
    id: string
    at: number
    category: string
    type: string
    summary: string
    severity: 'info' | 'warning' | 'error'
    source: string
    details: Record<string, unknown>
}

export interface HealthTimelineStatus {
    schema: number
    events: HealthTimelineEvent[]
    categories: string[]
    retention_days: number
    event_limit: number
    total_events: number
    updated_at: number
}
