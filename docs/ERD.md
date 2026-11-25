# ERD logis

Setiap diagram menampilkan satu area kerja. Hubungan lintas area menggunakan nama entitas yang sama. Kardinalitas menjelaskan jalur rancangan dan validasi tambahan dicatat dalam skema.

## Akademik dan kompetensi

```mermaid
erDiagram
    Institution ||--o{ StudyProgram : terkait
    Institution ||--o{ InstitutionAffiliation : terkait
    User ||--o{ InstitutionAffiliation : terkait
    User ||--o{ Learner : terkait
    InstitutionAffiliation ||--o{ ProgramAffiliation : terkait
    StudyProgram ||--o{ ProgramAffiliation : terkait
    StudyProgram ||--o{ Curriculum : terkait
    StudyProgram ||--o{ AcademicPeriod : terkait
    StudyProgram ||--o{ Cohort : terkait
    StudyProgram ||--o{ Learner : terkait
    StudyProgram ||--o{ RoleGrant : terkait
    EducationStage ||--o{ StudyProgram : terkait
    Curriculum ||--o{ CurriculumVersion : terkait
    CurriculumVersion ||--o{ CurriculumStage : terkait
    CurriculumStage ||--o{ Placement : terkait
    Cohort ||--o{ LearnerEnrollment : terkait
    Learner ||--o{ LearnerEnrollment : terkait
    Learner ||--o{ AdvisorAssignment : terkait
    LearnerEnrollment ||--o{ AcademicAssignment : terkait
    LearnerEnrollment ||--o{ LearnerEvidencePlan : terkait
    AcademicPeriod ||--o{ Placement : terkait
    AcademicPeriod ||--o{ LearnerEnrollment : terkait
    Placement ||--o{ AcademicAssignment : terkait
    ProgramAffiliation ||--o{ AcademicAssignment : terkait
    ProgramAffiliation ||--o{ AdvisorAssignment : terkait
    StudyProgram ||--o| CompetencyFramework : terkait
    StudyProgram ||--o| AssessmentBlueprint : terkait
    StudyProgram ||--o| ArtifactMap : terkait
    CompetencyFramework ||--o{ CompetencyFrameworkVersion : terkait
    CompetencyFrameworkVersion ||--o{ CompetencyItem : terkait
    CompetencyFrameworkVersion ||--o{ CompetencyRelationship : terkait
    CompetencyItem o|--o{ CompetencyItem : terkait
    CompetencyItem ||--o{ CompetencyIndicator : terkait
    CompetencyItem ||--o{ CompetencyMilestone : terkait
    CompetencyItem ||--o{ CompetencyRelationship : terkait
    CompetencyItem ||--o{ PerformanceStandard : terkait
    CurriculumStage ||--o{ CompetencyMilestone : terkait
    PerformanceStandard ||--o{ PerformanceStandardVersion : terkait
```

## Asesmen, sumber, peta dan bukti

```mermaid
erDiagram
    AssessmentBlueprint ||--o{ AssessmentBlueprintVersion : terkait
    AssessmentBlueprintVersion ||--o{ BlueprintItem : terkait
    AssessmentMethod ||--o{ BlueprintItem : terkait
    AssessmentMethod ||--o{ AssessmentEvent : terkait
    BlueprintItem ||--o{ BlueprintItemCompetency : terkait
    BlueprintItem ||--o{ AssessmentSamplingRule : terkait
    BlueprintItem ||--o{ AssessmentEvent : terkait
    BlueprintItem ||--o{ EvidenceRequirementOrigin : terkait
    CompetencyItem ||--o{ BlueprintItemCompetency : terkait
    CompetencyIndicator o|--o{ BlueprintItemCompetency : terkait
    AssessmentEvent ||--o{ AssessmentParticipation : terkait
    LearnerEnrollment ||--o{ AssessmentParticipation : terkait
    AssessmentParticipation ||--o{ AssessmentAttempt : terkait
    AssessmentAttempt ||--o{ AssessmentResult : terkait
    AssessmentResult ||--o{ AssessmentResultComponent : terkait
    StudyProgram ||--o{ EvidenceSource : terkait
    StudyProgram ||--o{ EvidenceType : terkait
    EvidenceSource ||--o{ EvidenceSourceCapability : terkait
    EvidenceSource ||--o{ EvidenceSourceCompetency : terkait
    EvidenceSource ||--o{ EvidenceSourceIntegration : terkait
    EvidenceSource ||--o{ EvidenceSourceMapping : terkait
    EvidenceSource ||--o{ EvidenceRequirementSource : terkait
    EvidenceSource ||--o{ EvidenceRecord : terkait
    EvidenceType ||--o{ EvidenceSourceCapability : terkait
    EvidenceType ||--o{ EvidenceRecord : terkait
    CompetencyItem ||--o{ EvidenceSourceCompetency : terkait
    ArtifactMap ||--o{ ArtifactMapVersion : terkait
    ArtifactMapVersion ||--o{ ArtifactMapItem : terkait
    ArtifactMapVersion ||--o{ LearnerEvidencePlan : terkait
    ArtifactMapItem ||--o{ ArtifactMapItemCompetency : terkait
    ArtifactMapItem ||--o{ EvidenceRequirementTemplate : terkait
    CompetencyItem ||--o{ ArtifactMapItemCompetency : terkait
    CompetencyItem ||--o{ EvidenceRequirementCompetency : terkait
    EvidenceRequirementTemplate ||--o{ EvidenceRequirementCompetency : terkait
    EvidenceRequirementTemplate ||--o{ EvidenceRequirementOrigin : terkait
    EvidenceRequirementTemplate ||--o{ EvidenceRequirementSource : terkait
    EvidenceRequirementTemplate ||--o{ LearnerEvidenceRequirement : terkait
    FulfillmentRule ||--o{ FulfillmentRuleVersion : terkait
    FulfillmentRuleVersion ||--o{ EvidenceRequirementTemplate : terkait
    FulfillmentRuleVersion ||--o{ RequirementRevision : terkait
    LearnerEvidencePlan ||--o{ LearnerEvidenceRequirement : terkait
    LearnerEvidencePlan ||--o{ AdaptivePlanRevision : terkait
    LearnerEvidenceRequirement ||--o{ RequirementRevision : terkait
    LearnerEvidenceRequirement ||--o{ RequirementEvidenceLink : terkait
    LearnerEnrollment ||--o{ EvidenceRecord : terkait
    EvidenceRecord ||--o{ EvidenceRecordRevision : terkait
    EvidenceRecord ||--o{ RequirementEvidenceLink : terkait
    EvidenceRecord ||--o{ ReflectionEvidenceLink : terkait
    EvidenceRecord ||--o{ SensemakingEvidenceLink : terkait
    EvidenceRecordRevision ||--o{ EvidenceArtifact : terkait
    EvidenceRecordRevision ||--o{ EvidenceCompetencyLink : terkait
    EvidenceRecordRevision ||--o{ EvidenceObservation : terkait
    EvidenceRecordRevision ||--o{ EvidenceScore : terkait
    EvidenceRecordRevision ||--o{ EvidenceFeedback : terkait
    EvidenceRecordRevision ||--o{ EvidenceVerification : terkait
    EvidenceRecordRevision ||--o{ EvidenceProvenance : terkait
    EvidenceRecordRevision ||--o{ EvidenceContext : terkait
    AssessmentAttempt o|--o{ EvidenceProvenance : terkait
    CompetencyItem ||--o{ EvidenceCompetencyLink : terkait
    CompetencyIndicator o|--o{ EvidenceCompetencyLink : terkait
```

## Evaluasi dan adaptasi

```mermaid
erDiagram
    StudyProgram ||--o{ EvaluationRuleSet : terkait
    StudyProgram ||--o{ AdaptivePolicy : terkait
    EvaluationRuleSet ||--o{ EvaluationRuleSetVersion : terkait
    EvaluationRuleSetVersion ||--o{ EvaluationRule : terkait
    EvaluationRuleSetVersion ||--o{ EvidenceEvaluation : terkait
    PerformanceStandardVersion ||--o{ EvidenceEvaluation : terkait
    CompetencyItem ||--o{ EvidenceEvaluation : terkait
    CompetencyItem ||--o{ AdditionalAttemptTarget : terkait
    LearnerEnrollment ||--o{ EvidenceEvaluation : terkait
    EvidenceEvaluation ||--o{ EvaluationFinding : terkait
    EvidenceEvaluation ||--o{ EvaluationEvidenceLink : terkait
    EvidenceEvaluation ||--o{ EvidenceGap : terkait
    EvidenceEvaluation ||--o{ PerformanceGapDecision : terkait
    EvidenceEvaluation ||--o{ AdaptivePlanRevision : terkait
    EvidenceRecordRevision ||--o{ EvaluationEvidenceLink : terkait
    PerformanceGap ||--o{ PerformanceGapDecision : terkait
    PerformanceGapDecision ||--o{ DecisionOverride : terkait
    PerformanceGapDecision ||--o{ LearningIntervention : terkait
    AdaptivePolicy ||--o{ AdaptivePolicyVersion : terkait
    AdaptivePolicyVersion ||--o{ AdaptivePlanRevision : terkait
    AdaptivePlanRevision ||--o{ AdditionalAttemptRequirement : terkait
    AdaptivePlanRevision ||--o{ EscalationRecord : terkait
    AdditionalAttemptRequirement ||--o{ AdditionalAttemptTarget : terkait
    AdditionalAttemptRequirement ||--o{ AdditionalAttemptAssignment : terkait
    AdditionalAttemptRequirement ||--o{ AdditionalAttemptFulfillment : terkait
    EvidenceGap ||--o{ AdditionalAttemptTarget : terkait
    AssessmentAttempt ||--o{ AdditionalAttemptFulfillment : terkait
```

## Refleksi, coaching dan pembelajaran

```mermaid
erDiagram
    StudyProgram ||--o{ ReflectionPrompt : terkait
    ReflectionPrompt ||--o{ ReflectionPromptVersion : terkait
    ReflectionPromptVersion ||--o{ ReflectionTriggerRule : terkait
    ReflectionPromptVersion ||--o{ ReflectionTask : terkait
    LearnerEnrollment ||--o{ ReflectionTask : terkait
    LearnerEnrollment ||--o{ ReflectionEntry : terkait
    LearnerEnrollment ||--o{ SensemakingReview : terkait
    LearnerEnrollment ||--o{ LearnerSelfAssessment : terkait
    LearnerEnrollment ||--o{ IndividualLearningPlan : terkait
    ReflectionTask o|--o{ ReflectionEntry : terkait
    ReflectionEntry ||--o{ ReflectionRevision : terkait
    ReflectionEntry ||--o{ ReflectionAccessGrant : terkait
    ReflectionRevision ||--o{ ReflectionEvidenceLink : terkait
    ReflectionRevision ||--o{ ReflectionCompetencyLink : terkait
    ReflectionRevision ||--o{ ReflectionFeedbackLink : terkait
    ReflectionRevision ||--o{ ReflectionDecisionLink : terkait
    ReflectionRevision ||--o{ ReflectionLearningGoalLink : terkait
    CompetencyItem ||--o{ ReflectionCompetencyLink : terkait
    EvidenceFeedback ||--o{ ReflectionFeedbackLink : terkait
    ProgressionDecision ||--o{ ReflectionDecisionLink : terkait
    LearningGoal ||--o{ ReflectionLearningGoalLink : terkait
    SensemakingReview ||--o{ SensemakingReviewRevision : terkait
    SensemakingReviewRevision ||--o{ SensemakingEvidenceLink : terkait
    EvidenceEvaluation ||--o{ AutomatedEvidenceSummary : terkait
    AdvisorAssignment ||--o{ CoachingRelationship : terkait
    CoachingRelationship ||--o{ CoachingSession : terkait
    CoachingRelationship ||--o{ CoachingDialogue : terkait
    CoachingDialogue ||--o{ DialogueMessage : terkait
    CoachingDialogue ||--o{ CoachingRecommendation : terkait
    CoachingDialogue ||--o{ CoachingAction : terkait
    IndividualLearningPlan ||--o{ LearningGoal : terkait
    LearningGoal ||--o{ LearningGoalRevision : terkait
    LearningGoalRevision ||--o{ LearningGoalEvidenceLink : terkait
    EvidenceRecordRevision ||--o{ LearningGoalEvidenceLink : terkait
    LearningGoal ||--o{ LearningIntervention : terkait
    LearningActivity ||--o{ InterventionActivity : terkait
    LearningIntervention ||--o{ InterventionActivity : terkait
    LearningIntervention ||--o{ InterventionReview : terkait
    LearningIntervention ||--o{ ReassessmentPlan : terkait
    LearningIntervention ||--o{ ReassessmentRequirement : terkait
    ReassessmentPlan ||--o{ ReassessmentRequirement : terkait
    CompetencyItem ||--o{ ReassessmentRequirement : terkait
```

## EPA dan keputusan

```mermaid
erDiagram
    StudyProgram ||--o{ EntrustableProfessionalActivity : terkait
    StudyProgram ||--o{ SupervisionScale : terkait
    StudyProgram ||--o{ ProgressionReview : terkait
    EntrustableProfessionalActivity ||--o{ EPAVersion : terkait
    EPAVersion ||--o{ EPACompetencyLink : terkait
    EPAVersion ||--o{ EPAMilestone : terkait
    EPAVersion ||--o{ EPAScope : terkait
    EPAVersion ||--o{ EPALimitation : terkait
    EPAVersion ||--o{ EPAObservation : terkait
    EPAVersion ||--o{ EntrustmentReview : terkait
    CompetencyItem ||--o{ EPACompetencyLink : terkait
    SupervisionScale ||--o{ SupervisionScaleVersion : terkait
    SupervisionScaleVersion ||--o{ EPAObservation : terkait
    SupervisionScaleVersion ||--o{ EntrustmentReview : terkait
    LearnerEnrollment ||--o{ EPAObservation : terkait
    LearnerEnrollment ||--o{ EntrustmentReview : terkait
    LearnerEnrollment ||--o{ CompetencyReview : terkait
    LearnerEnrollment ||--o{ ProgressionReview : terkait
    EntrustmentReview ||--o{ EntrustmentDecision : terkait
    EPAObservation ||--o{ DecisionEvidenceLink : terkait
    EvidenceRecordRevision ||--o{ DecisionEvidenceLink : terkait
    EntrustmentDecision ||--o{ DecisionEvidenceLink : terkait
    CompetencyReview ||--o{ CompetencyAttainment : terkait
    ProgressionReview ||--o{ ProgressionDecision : terkait
    ProgressionDecision ||--o{ DecisionEvidenceLink : terkait
    ProgressionDecision ||--o{ DecisionParticipant : terkait
    User ||--o{ DecisionParticipant : terkait
    User ||--o{ CommitteeMembership : terkait
```

## Infrastruktur

```mermaid
erDiagram
    User ||--o{ RoleGrant : terkait
    User ||--o{ AuditEvent : terkait
    User ||--o{ DataAccessEvent : terkait
    User ||--o{ Notification : terkait
    User ||--o{ NotificationPreference : terkait
    StudyProgram o|--o{ RoleGrant : terkait
    StudyProgram o|--o{ AuditEvent : terkait
    StudyProgram o|--o{ DataAccessEvent : terkait
    Institution o|--o{ RoleGrant : terkait
    EvidenceSourceIntegration ||--o{ IntegrationEvent : terkait
    IntegrationEvent o|--o{ DomainEvent : terkait
    DomainEvent o|--o{ OutboxEvent : terkait
    OutboxEvent ||--o{ BackgroundJob : terkait
```

## Relasi gabungan

Peta mengikat versi kerangka, blueprint, kurikulum dan aturan evaluasi. Persyaratan menyimpan asal melalui FK bertipe. Satu sumber asal atau bukti dapat memetakan banyak target melalui entitas penghubung.

Link keputusan memiliki tepat satu FK keputusan dan tepat satu FK item pendukung. Untuk entrustment, dukungan dapat berupa observasi EPA atau revisi bukti. Untuk progresi, dukungan berasal dari revisi bukti yang berlaku.

Link refleksi tetap mengikat identitas bukti dan revisi yang dibaca. Link evaluasi, pemenuhan dan keputusan menunjuk revisi bukti yang digunakan.
