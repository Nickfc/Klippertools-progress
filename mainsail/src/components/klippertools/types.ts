export interface NozzleGuardStatus {
    version: string
    ready: boolean
    state: 'no_file' | 'disabled' | 'unknown' | 'match' | 'mismatch' | 'overridden' | 'error'
    message: string
    mode: 'block' | 'warn' | 'off'
    blocking: boolean
    filename: string | null
    configured_nozzle: number
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
    progress: number
    state: 'good' | 'soon' | 'due'
    due: boolean
    snoozed: boolean
    estimated_due: number | null
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
    updated_at: number
}
