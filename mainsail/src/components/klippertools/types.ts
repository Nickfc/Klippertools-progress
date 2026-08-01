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
