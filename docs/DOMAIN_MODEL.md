# Model domain logis

Katalog mengikuti §7 instruksi induk. Tambahan rancangan mencakup akun, afiliasi, penempatan, pemberian akses, dan keanggotaan komite. Nama entitas merupakan rancangan konseptual. Lihat [ERD](ERD.md) untuk relasi dan [skema](DATABASE_SCHEMA.md) untuk atribut dan invariant.

## Academic domain

`Institution`, `StudyProgram`, `Curriculum`, `CurriculumVersion`, `AcademicPeriod`, `EducationStage`, `CurriculumStage`, `Cohort`, `Learner`, `LearnerEnrollment`, `AcademicAssignment`, `AdvisorAssignment`, `User`, `InstitutionAffiliation`, `ProgramAffiliation`, `Placement`.

## Competency domain

`CompetencyFramework`, `CompetencyFrameworkVersion`, `CompetencyItem`, `CompetencyIndicator`, `CompetencyRelationship`, `CompetencyMilestone`, `PerformanceStandard`, `PerformanceStandardVersion`.

## Assessment domain

`AssessmentBlueprint`, `AssessmentBlueprintVersion`, `AssessmentMethod`, `BlueprintItem`, `BlueprintItemCompetency`, `AssessmentSamplingRule`, `AssessmentEvent`, `AssessmentParticipation`, `AssessmentAttempt`, `AssessmentResult`, `AssessmentResultComponent`.

## Evidence source domain

`EvidenceSource`, `EvidenceType`, `EvidenceSourceCapability`, `EvidenceSourceCompetency`, `EvidenceSourceIntegration`, `EvidenceSourceMapping`.

## Artifact map and expected evidence domain

`ArtifactMap`, `ArtifactMapVersion`, `ArtifactMapItem`, `ArtifactMapItemCompetency`, `EvidenceRequirementTemplate`, `EvidenceRequirementSource`, `EvidenceRequirementCompetency`, `EvidenceRequirementOrigin`, `FulfillmentRule`, `FulfillmentRuleVersion`, `LearnerEvidencePlan`, `LearnerEvidenceRequirement`, `RequirementRevision`, `RequirementEvidenceLink`.

## Actual evidence domain

`EvidenceRecord`, `EvidenceRecordRevision`, `EvidenceArtifact`, `EvidenceCompetencyLink`, `EvidenceObservation`, `EvidenceScore`, `EvidenceFeedback`, `EvidenceVerification`, `EvidenceProvenance`, `EvidenceContext`.

## Evaluation domain

`EvaluationRuleSet`, `EvaluationRuleSetVersion`, `EvaluationRule`, `EvidenceEvaluation`, `EvaluationEvidenceLink`, `EvaluationFinding`, `EvidenceGap`, `PerformanceGap`, `PerformanceGapDecision`, `DecisionOverride`.

## Adaptive planning domain

`AdaptivePolicy`, `AdaptivePolicyVersion`, `AdaptivePlanRevision`, `AdditionalAttemptRequirement`, `AdditionalAttemptTarget`, `AdditionalAttemptAssignment`, `AdditionalAttemptFulfillment`, `EscalationRecord`.

## Reflection and sensemaking domain

`ReflectionPrompt`, `ReflectionPromptVersion`, `ReflectionTriggerRule`, `ReflectionTask`, `ReflectionEntry`, `ReflectionRevision`, `ReflectionEvidenceLink`, `ReflectionCompetencyLink`, `ReflectionFeedbackLink`, `SensemakingReview`, `SensemakingReviewRevision`, `SensemakingEvidenceLink`, `AutomatedEvidenceSummary`, `LearnerSelfAssessment`, `ReflectionDecisionLink`, `ReflectionLearningGoalLink`, `ReflectionAccessGrant`.

## Coaching domain

`CoachingRelationship`, `CoachingSession`, `CoachingDialogue`, `DialogueMessage`, `CoachingRecommendation`, `CoachingAction`.

## Learning development domain

`IndividualLearningPlan`, `LearningGoal`, `LearningGoalRevision`, `LearningGoalEvidenceLink`, `LearningActivity`, `LearningIntervention`, `InterventionActivity`, `InterventionReview`, `ReassessmentPlan`, `ReassessmentRequirement`.

## EPA domain

`EntrustableProfessionalActivity`, `EPAVersion`, `EPACompetencyLink`, `EPAMilestone`, `EPAScope`, `EPALimitation`, `EPAObservation`, `SupervisionScale`, `SupervisionScaleVersion`, `EntrustmentReview`, `EntrustmentDecision`.

## Progression domain

`CompetencyAttainment`, `CompetencyReview`, `ProgressionReview`, `ProgressionDecision`, `DecisionEvidenceLink`, `DecisionParticipant`.

## Infrastructure domain

`AuditEvent`, `DomainEvent`, `OutboxEvent`, `BackgroundJob`, `IntegrationEvent`, `Notification`, `NotificationPreference`, `DataAccessEvent`, `RoleGrant`, `CommitteeMembership`.
