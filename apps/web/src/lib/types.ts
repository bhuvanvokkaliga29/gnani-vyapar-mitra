/**
 * TypeScript Type Definitions for Phase 10 Merchant AI Control Center.
 * Matches backend schemas in services/dashboard/schemas.py
 */

export type RuntimeHealthStatus = 'HEALTHY' | 'ATTENTION_REQUIRED';
export type EvidenceClass = 'SIMULATED' | 'TEST_MODE_OBSERVED' | 'OBSERVED';
export type AttentionSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface AttentionItem {
  id: string;
  severity: AttentionSeverity;
  title: string;
  description: string;
  entity_id?: string | null;
  count: number;
  timestamp: string;
  action_hint?: string | null;
}

export interface ActivePolicySummary {
  policy_id: string;
  policy_version: string;
  strategy_type: string;
  lifecycle_status: string;
  observed_contribution_paise: number;
  evidence_count: number;
  context_coverage_count: number;
  promoted_at?: string | null;
}

export interface LearningInsight {
  buyer_context_key: string;
  context_description: string;
  observed_preference_strategy: string;
  evidence_count: number;
  context_coverage_count: number;
  observed_contribution_paise: number;
  evidence_strength: 'HIGH' | 'MODERATE' | 'COLD_START';
  evidence_class: EvidenceClass;
}

export interface RecentDecisionItem {
  decision_id: string;
  opportunity_id: string;
  created_at: string;
  buyer_context_key: string;
  selected_strategy_type: string;
  proposed_price_paise: number;
  decision_mode: string;
  execution_status: string;
  outcome_status?: string | null;
  learning_eligible: boolean;
}

export interface DashboardOverview {
  merchant_id: string;
  merchant_name: string;
  currency: string;
  runtime_status: RuntimeHealthStatus;
  status_headline: string;
  status_subtext: string;
  ai_buyer_opportunities_count: number;
  decision_count: number;
  authorized_executions_count: number;
  paid_transactions_count: number;
  expected_contribution_paise: number;
  observed_contribution_paise: number;
  test_mode_observed_contribution_paise: number;
  decision_rate_percent: number;
  total_learning_observations_count?: number;
  total_contexts_count?: number;
  active_policy?: ActivePolicySummary | null;
  learning_insight?: LearningInsight | null;
  attention_items: AttentionItem[];
  recent_decisions: RecentDecisionItem[];
  generated_at: string;
}

export interface DecisionBuyerOfferView {
  offer_title: string;
  product_ids: string[];
  offer_price_paise: number;
  currency: string;
  strategy_type: string;
  warranty_months: number;
  delivery_days: number;
  included_items: string[];
}

export interface DecisionMerchantEvaluation {
  cogs_paise: number;
  gross_profit_paise: number;
  gross_margin_percent: number;
  predicted_contribution_paise: number;
  uncertainty: number;
  composite_ranking_score: number;
  decision_mode: string;
  rationale: string;
}

export interface DecisionCandidate {
  candidate_id: string;
  strategy_type: string;
  proposed_price_paise: number;
  predicted_contribution_paise: number;
  uncertainty: number;
  composite_ranking_score: number;
  is_selected: boolean;
}

export interface IntentSummary {
  category?: string;
  use_case?: string;
  quantity?: number;
  budget_paise?: number;
  hard_requirements?: string[];
  preferences?: string[];
  exclusions?: string[];
  raw_prompt?: string | null;
}

export interface DecisionDetail {
  decision_id: string;
  request_id?: string | null;
  merchant_id: string;
  opportunity_id: string;
  buyer_context_key: string;
  created_at: string;
  raw_prompt?: string | null;
  intent_summary?: IntentSummary | null;
  authorization_id?: string | null;
  execution_id?: string | null;
  order_id?: string | null;
  razorpay_order_id?: string | null;
  authorized_amount_paise?: number | null;
  payment_id?: string | null;
  outcome_id?: string | null;
  evidence_id?: string | null;
  memory_id?: string | null;
  applied_observation_id?: string | null;
  buyer_offer: DecisionBuyerOfferView;
  merchant_evaluation: DecisionMerchantEvaluation;
  candidates: DecisionCandidate[];
  safety_status: string;
  safety_rejection_reasons: string[];
  execution_status: string;
  transaction_state?: string | null;
  outcome_status?: string | null;
  learning_eligible: boolean;
  reward_contribution_paise?: number | null;
}

export interface DecisionListResponse {
  items: RecentDecisionItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PolicyVersionItem {
  policy_id: string;
  version_id: string;
  strategy_type: string;
  lifecycle_status: string;
  created_at: string;
  promoted_at?: string | null;
  evidence_count: number;
  observed_contribution_paise: number;
  promotion_criteria_satisfied: boolean;
  is_active: boolean;
}

export interface PolicyTransitionItem {
  transition_id: string;
  policy_id: string;
  from_state: string;
  to_state: string;
  action: string;
  reason: string;
  timestamp: string;
  performed_by: string;
}

export interface PolicyManagement {
  merchant_id: string;
  active_policy?: ActivePolicySummary | null;
  versions: PolicyVersionItem[];
  recent_transitions: PolicyTransitionItem[];
}

export interface ExperimentItem {
  experiment_id: string;
  name: string;
  status: string;
  source: EvidenceClass;
  control_policy_id: string;
  treatment_policy_id: string;
  population_size: number;
  control_observed_ecps_paise?: number | null;
  treatment_observed_ecps_paise?: number | null;
  observed_diff_paise?: number | null;
  guardrail_status: string;
  created_at: string;
  completed_at?: string | null;
}

export interface ExperimentListResponse {
  items: ExperimentItem[];
  total: number;
}

export interface LearningHealth {
  eligible_opportunities_count: number;
  valid_evidence_count: number;
  rejected_evidence_count: number;
  memory_observations_count: number;
  model_updates_count: number;
  duplicate_observations_count: number;
}

export interface ContextLearningItem {
  buyer_context_key: string;
  context_label: string;
  preferred_strategy: string;
  evidence_count: number;
  observed_contribution_paise: number;
  last_updated_at: string;
  status: string;
}

export interface LearningModelMetadata {
  model_version: string;
  algorithm_version: string;
  feature_version: string;
  dimension: number;
  lambda_reg: number;
  alpha_paise: number;
  observation_count: number;
  version: number;
  last_updated_at: string;
  learning_status: string;
}

export interface LearningCenter {
  merchant_id: string;
  health: LearningHealth;
  context_breakdown: ContextLearningItem[];
  model_metadata: LearningModelMetadata;
  evidence_class: EvidenceClass;
}

export interface ActivityEventItem {
  audit_event_id: string;
  timestamp: string;
  entity_type: string;
  action: string;
  opportunity_id?: string | null;
  decision_id?: string | null;
  execution_id?: string | null;
  summary: string;
  details: Record<string, any>;
}

export interface ActivityListResponse {
  items: ActivityEventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OpportunityTrace {
  trace_version: string;
  merchant_id: string;
  opportunity_id: string;
  request_id?: string | null;
  decision_id?: string | null;
  execution_id?: string | null;
  order_id?: string | null;
  payment_id?: string | null;
  outcome_id?: string | null;
  evidence_id?: string | null;
  memory_id?: string | null;
  applied_observation_id?: string | null;
  trace_status: string;
  stopped_reason?: string | null;
  stages_present: string[];
  audit_event_count: number;
}

export interface ControlActionResponse {
  success: boolean;
  action: string;
  policy_id: string;
  message: string;
  audit_event_id?: string | null;
  timestamp: string;
}
