# TITENI — MASTER DEVELOPMENT INSTRUCTION

## 1. Project mandate

Develop the existing Titeni application into a comprehensive **Adaptive Reflective E-Portfolio and Competency Development System** for medical and health professions education.

The application foundation already exists using:

- Django
- Tailwind CSS (use oxbow, https://github.com/michael-andreuzza/oxbow)
- PostgreSQL
- uv for Python environment and dependency management

The development environment uses macOS with MacPorts, not Homebrew. PostgreSQL 18.6 and uv are already installed.

Recreate the project, replace the existing technology stack, and reinstall existing infrastructure when necessary. But, keep the UI intact.

Replace or reset all existing repository, application architecture, dependencies, database models, migrations, authentication, templates, and configuration before implementing changes.

Use **Titeni** consistently as the application name.

## 2. Educational philosophy

Titeni is not merely a digital portfolio, assessment repository, logbook, gradebook, or document management system.

Titeni is a competency-centered, evidence-driven, adaptive, reflective, and longitudinal educational system.

Its governing principle is:

**Fixed competency expectations, adaptive evidence acquisition, reflective sensemaking, and defensible progression decisions.**

The system must support:

- Assessment of learning.
- Assessment for learning.
- Assessment as learning.
- Programmatic assessment.
- Competency-based education.
- Self-regulated learning.
- Reflective practice.
- Longitudinal competency development.
- Evidence-informed educational decisions.

The ultimate outcome is not portfolio completion or artifact accumulation.

The ultimate outcome is the development of competence, supported by sufficient evidence, meaningful reflection, feedback, targeted learning interventions, and defensible educational decisions.

## 3. Non-negotiable conceptual distinctions

Maintain explicit separation between:

1. Competency expectations.
2. Expected evidence.
3. Actual evidence.
4. Evidence sufficiency.
5. Performance attainment.
6. Performance gap.
7. Evidence gap.
8. Additional assessment attempts.
9. Learning interventions.
10. Reassessment.
11. Reflection and sensemaking.
12. Formal progression decisions.

Evidence sufficiency means that sufficient information is available to determine whether a performance gap has been closed.

Evidence sufficiency does not mean that the learner has achieved competence.

Implement the following decision logic:

| Evidence sufficiency | Performance gap | Required action |
|---|---|---|
| Insufficient | Undetermined | Adaptive additional evidence acquisition |
| Sufficient | Open | Learning intervention followed by reassessment |
| Sufficient | Closed | Document attainment and consider progression |

The system must never infer incompetence solely from missing evidence.

The system must never infer competence solely from completed evidence requirements.

Do not repeatedly prescribe additional assessments when existing evidence already establishes a performance gap requiring learning intervention.

## 4. Academic scope

Support the following educational stages:

- Undergraduate — Sarjana.
- Professional — Profesi.
- Specialist — Spesialis.
- Subspecialist — Subspesialis.

Each Titeni installation serves exactly one Faculty of Medicine and supports multiple study programs within that faculty. Keep academic structures configurable per study program.

Each study program owns its competency framework and macro assessment blueprint.

A study program has one logical macro assessment blueprint with multiple historical versions.

Competency frameworks, curricula, blueprints, milestones, and evaluation rules must be versioned.

Historical learner records must remain interpretable according to the academic configurations applicable when the evidence was generated.

## 5. High-level system architecture

Implement the following interconnected domains:

1. Academic and institutional management.
2. Competency framework management.
3. Curriculum and milestone management.
4. Macro assessment blueprint management.
5. Evidence source registry.
6. Master artifact map.
7. Expected evidence management.
8. Individual evidence planning.
9. Actual evidence acquisition.
10. Evidence verification and provenance.
11. Evidence sufficiency evaluation.
12. Performance gap evaluation.
13. Adaptive additional attempt planning.
14. Reflection and sensemaking.
15. Feedback and coaching.
16. Individual learning planning.
17. Learning intervention and reassessment.
18. EPA management.
19. Competency and progression decisions.
20. Program analytics.
21. Integration management.
22. Authorization and audit management.

Use a modular Django architecture.

Prefer a modular monolith rather than premature microservices.

Organize modules according to educational domain boundaries, not merely CRUD entities.

## 6. Business process

Implement the following end-to-end business processes.

### BP-01 — Academic configuration

Configure institutions, study programs, curricula, academic periods, educational stages, cohorts, rotations, users, and academic relationships.

### BP-02 — Competency framework configuration

Configure:

- Graduate outcomes.
- Competency domains.
- Competencies.
- Subcompetencies.
- Competency indicators.
- Performance standards.
- Developmental milestones.
- Competency relationships.
- Prerequisites.
- Stage-specific expectations.

Support hierarchical competency structures and many-to-many developmental relationships.

### BP-03 — Macro assessment blueprint configuration

Register the complete program-level assessment blueprint.

Each blueprint component may specify:

- Assessment method.
- Assessment purpose.
- Curriculum stage.
- Assessment timing.
- Competency mapping.
- Indicator mapping.
- Sampling requirements.
- Context requirements.
- Expected evidence types.
- Expected evidence granularity.
- Assessment frequency.
- Minimum performance standard.
- Evidence source.
- Responsible actor.

Separate assessment design from actual assessment events and individual attempts.

A single assessment event may generate multiple evidence records.

### BP-04 — Other evidence source registration

Register evidence sources outside formal assessment.

Examples include:

- LMS activities.
- Clinical logbooks.
- Clinical encounters.
- Workplace observations.
- Research activities.
- Projects.
- Case reports.
- Reflective writing.
- Patient feedback.
- Peer feedback.
- Supervisor feedback.
- Professional activities.
- Learning contracts.
- Student-generated artifacts.
- Interprofessional activities.

Every evidence source must specify what evidence it can generate, how it is acquired, how it is verified, and what competencies it can support.

### BP-05 — Master artifact map generation

Generate the Master Artifact Map by integrating:

- Competency framework.
- Macro assessment blueprint.
- Other evidence sources.
- Developmental milestones.
- Evidence requirements.
- Evidence evaluation rules.

The Master Artifact Map is a program-level representation of the expected evidence architecture.

It must identify competency coverage, evidence sources, evidence requirements, and gaps in the program-level assessment design.

Allow authorized academic users to supplement automatically derived mappings with manually configured mappings.

Use a hybrid expected evidence model:

- Blueprint-derived requirements.
- Manually configured requirements.
- Requirements derived from other evidence sources.
- Conditional requirements.
- Optional supplementary evidence.

### BP-06 — Individual evidence plan initialization

When a learner enters a program, stage, semester, block, or rotation, automatically generate an Individual Evidence Plan.

The plan must contain:

- Applicable competency expectations.
- Initial expected evidence.
- Expected evidence sources.
- Required quantity.
- Required context and coverage.
- Verification requirements.
- Due dates.
- Fulfillment rules.
- Applicable evaluation rules.
- Responsible actors.

Preserve the original baseline plan.

Subsequent adaptive requirements must be recorded separately from the baseline.

### BP-07 — Actual evidence acquisition

Acquire evidence through:

- Native assessment forms.
- External assessment systems.
- LMS integration.
- Clinical logbooks.
- Student submissions.
- Supervisor observations.
- File uploads.
- Structured imports.
- APIs.
- Manual authorized entry.

Each evidence record must have identifiable provenance.

Validate evidence before counting it toward fulfillment.

Support one evidence record contributing to multiple competency indicators and multiple requirements when academically appropriate.

### BP-08 — Evidence reconciliation

Automatically match actual evidence against expected evidence requirements.

Evaluate:

- Source eligibility.
- Evidence type.
- Learner identity.
- Competency mapping.
- Context.
- Timing.
- Verification.
- Duplication.
- Applicable rule versions.

Prevent duplicate evidence from inflating fulfillment.

Do not count unverified evidence when verification is required.

### BP-09 — Evidence sufficiency evaluation

Evaluate whether available evidence is sufficient to support a defensible performance decision.

Evaluate relevant dimensions:

- Quantity.
- Coverage.
- Quality.
- Authenticity.
- Context diversity.
- Assessor diversity.
- Recency.
- Consistency.
- Triangulation.
- Measurement uncertainty.
- Decision consequences.

Do not reduce evidence sufficiency to artifact counts or arithmetic averages.

Support different sufficiency criteria for different competencies, stages, assessment methods, and decision purposes.

Allow asymmetric sufficiency rules for concluding that a performance gap is open versus closed.

### BP-10 — Adaptive additional attempt planning

When evidence is insufficient, automatically calculate the required additional attempts.

This is a core application function.

The system must not merely display an evidence gap or recommend that an administrator manually add requirements.

It must automatically adjust the learner's Individual Evidence Plan according to approved adaptive rules.

Each additional attempt must specify:

- Target competency or indicator.
- Reason for the additional attempt.
- Evidence gap being addressed.
- Required evidence type.
- Eligible evidence source.
- Assessment method.
- Required context.
- Required assessor characteristics, where applicable.
- Priority.
- Due date or scheduling requirement.
- Fulfillment criteria.

Additional attempts must be targeted.

Do not assume that every evidence gap requires repetition of the same assessment method.

A single additional attempt may address multiple evidence gaps.

Avoid redundant additional attempts when an already planned attempt can address the same gap.

Recalculate requirements after each relevant evidence event.

Allow the number of outstanding additional attempts to increase, decrease, or become zero.

Cancel or supersede redundant unperformed attempts while preserving their history.

Never delete completed attempts or historical evidence.

Stop automatic evidence acquisition when sufficient evidence has been obtained.

Escalate to an authorized academic reviewer when automatic rules cannot resolve uncertainty, when additional attempts are unavailable, or when configured limits are reached.

### BP-11 — Performance gap evaluation

When evidence is sufficient, evaluate performance against the applicable competency standard.

Possible outcomes:

- Performance gap closed.
- Performance gap open.

When evidence is insufficient, performance attainment remains undetermined.

Maintain a distinction between automated rule-based findings and formal academic decisions.

High-stakes decisions must remain subject to appropriate human authorization.

### BP-12 — Reflective sensemaking

Reflection and sensemaking are core processes, not optional notes attached to assessment records.

Support three levels:

1. Artifact-level reflection.
2. Competency-level sensemaking.
3. Longitudinal reflection.

Support reflection triggers based on:

- New evidence.
- New assessment results.
- New feedback.
- Evidence inconsistencies.
- Confirmed performance gaps.
- Significant clinical experiences.
- Completion of learning interventions.
- Academic milestones.
- Scheduled coaching sessions.
- Learner-initiated reflection.

The system must automatically generate structured evidence summaries as interpretive scaffolds.

These summaries may include:

- Evidence collected.
- Relevant competency expectations.
- Performance trends.
- Strengths.
- Inconsistencies.
- Missing evidence.
- Feedback themes.
- Differences between self-assessment and external assessment.
- Previous learning goals.
- Progress since previous reviews.

Clearly distinguish automatically generated summaries from learner-authored interpretations.

Never generate a learner's personal reflection and represent it as the learner's own work.

Allow learners to interpret, challenge, contextualize, and revise their understanding of evidence.

Support configurable reflection prompts, including:

- What happened?
- What does this evidence mean?
- What does it reveal about my current competence?
- What explains the observed performance?
- What assumptions should I reconsider?
- What have I learned?
- What should I do differently?
- What evidence would demonstrate improvement?

Reflection must be linkable to multiple evidence records, competencies, feedback records, decisions, and learning goals.

Preserve reflection revisions and longitudinal development.

### BP-13 — Feedback and coaching dialogue

Support meaningful dialogue between learners and authorized advisors, mentors, supervisors, or coaches.

Allow coaches to:

- Review evidence.
- Review learner reflections.
- Challenge interpretations.
- Provide alternative perspectives.
- Discuss performance gaps.
- Support goal formulation.
- Recommend learning activities.
- Review progress.
- Document agreed actions.

Support threaded dialogue and follow-up.

Distinguish formative coaching records from formal summative decisions.

Support configurable confidentiality and visibility policies.

Do not automatically expose confidential formative reflections to summative decision-makers.

### BP-14 — Individual learning plan

Generate and maintain an Individual Learning Plan.

Learning goals may originate from:

- Learner reflection.
- Coaching dialogue.
- Confirmed performance gaps.
- Formal academic recommendations.
- Self-assessment.
- Previous learning interventions.

Each learning goal should include:

- Target competency.
- Rationale.
- Learning activity.
- Expected outcome.
- Required evidence of improvement.
- Responsible actor.
- Timeline.
- Review schedule.
- Completion criteria.

Support learner ownership of the learning plan while allowing appropriate academic oversight.

### BP-15 — Learning intervention

When sufficient evidence confirms an open performance gap, initiate the learning intervention pathway.

Do not simply prescribe repeated assessment without addressing the learning need.

Support:

- Targeted learning activities.
- Deliberate practice.
- Supervised clinical experience.
- Guided reading.
- Case discussion.
- Simulation.
- Remediation.
- Mentoring.
- Feedback.
- Other configurable educational interventions.

Automatically generate intervention requirements only where approved rules authorize them.

Allow academic advisors to personalize intervention plans.

### BP-16 — Reassessment

Following an intervention, generate targeted reassessment requirements.

Reassessment must evaluate whether the identified performance gap has been closed.

Preserve previous evidence and decisions.

Support rules that distinguish historical evidence from current evidence of performance.

Return reassessment evidence to the evidence reconciliation and sufficiency evaluation process.

### BP-17 — Longitudinal competency review

Provide integrated review of:

- Expected evidence.
- Actual evidence.
- Evidence sufficiency.
- Performance attainment.
- Historical performance gaps.
- Additional attempts.
- Learning interventions.
- Reassessment.
- Learner reflections.
- Coaching dialogue.
- Learning goals.
- Developmental milestones.

Allow authorized reviewers to synthesize evidence across time and contexts.

### BP-18 — Formal progression decision

Support formal academic decisions by authorized individuals or committees.

Examples include:

- Progression approved.
- Conditional progression.
- Additional learning required.
- Further evidence required.
- Progression deferred.
- Competency attainment approved.
- Entrustment decision.

Record decision rationale, supporting evidence, applicable standards, decision-makers, and decision date.

Do not allow the adaptive engine to independently issue high-stakes academic decisions.

### BP-19 — Program-level continuous improvement

Aggregate learner data to identify:

- Competencies with recurrent evidence gaps.
- Competencies with recurrent performance gaps.
- Insufficient blueprint sampling.
- Excessive additional assessment burden.
- Limited learning opportunities.
- Inconsistent assessment patterns.
- Evidence source reliability.
- Effectiveness of learning interventions.
- Time required to reach sufficient evidence.
- Time required to close performance gaps.

Use these findings to inform future curriculum and assessment blueprint revisions.

## 7. Logical database architecture

Use the following proposed entities as a logical model.

These names are not instructions to blindly create duplicate tables. Inspect existing Django models and reconcile the proposed architecture with existing implementations.

### 7.1 Academic domain

- Institution
- StudyProgram
- Curriculum
- CurriculumVersion
- AcademicPeriod
- EducationStage
- CurriculumStage
- Cohort
- Learner
- LearnerEnrollment
- AcademicAssignment
- AdvisorAssignment

### 7.2 Competency domain

- CompetencyFramework
- CompetencyFrameworkVersion
- CompetencyItem
- CompetencyIndicator
- CompetencyRelationship
- CompetencyMilestone
- PerformanceStandard
- PerformanceStandardVersion

Support hierarchical competency items and version-specific relationships.

### 7.3 Assessment domain

- AssessmentBlueprint
- AssessmentBlueprintVersion
- AssessmentMethod
- BlueprintItem
- BlueprintItemCompetency
- AssessmentSamplingRule
- AssessmentEvent
- AssessmentParticipation
- AssessmentAttempt
- AssessmentResult
- AssessmentResultComponent

Separate blueprint items, actual events, learner participation, attempts, and results.

### 7.4 Evidence source domain

- EvidenceSource
- EvidenceType
- EvidenceSourceCapability
- EvidenceSourceCompetency
- EvidenceSourceIntegration
- EvidenceSourceMapping

### 7.5 Artifact map and expected evidence domain

- ArtifactMap
- ArtifactMapVersion
- ArtifactMapItem
- ArtifactMapItemCompetency
- EvidenceRequirementTemplate
- EvidenceRequirementSource
- EvidenceRequirementCompetency
- EvidenceRequirementOrigin
- FulfillmentRule
- FulfillmentRuleVersion
- LearnerEvidencePlan
- LearnerEvidenceRequirement
- RequirementRevision
- RequirementEvidenceLink

Preserve requirement origin, including blueprint-derived and manually configured requirements.

Avoid generating duplicate requirements when blueprint-derived and manual mappings overlap.

### 7.6 Actual evidence domain

- EvidenceRecord
- EvidenceRecordRevision
- EvidenceArtifact
- EvidenceCompetencyLink
- EvidenceObservation
- EvidenceScore
- EvidenceFeedback
- EvidenceVerification
- EvidenceProvenance
- EvidenceContext

Each evidence record must have a learner, source, evidence type, occurrence date, acquisition date, provenance, and verification state.

Support evidence correction, supersession, and invalidation without destroying historical records.

### 7.7 Evaluation domain

- EvaluationRuleSet
- EvaluationRuleSetVersion
- EvaluationRule
- EvidenceEvaluation
- EvaluationEvidenceLink
- EvaluationFinding
- EvidenceGap
- PerformanceGap
- PerformanceGapDecision
- DecisionOverride

Each evaluation must preserve:

- Learner.
- Evaluation target.
- Applicable competency standard.
- Applicable rule version.
- Evidence snapshot or immutable evidence revisions.
- Evaluation findings.
- Sufficiency outcome.
- Evaluation timestamp.
- Engine version.
- Decision rationale.

### 7.8 Adaptive planning domain

- AdaptivePolicy
- AdaptivePolicyVersion
- AdaptivePlanRevision
- AdditionalAttemptRequirement
- AdditionalAttemptTarget
- AdditionalAttemptAssignment
- AdditionalAttemptFulfillment
- EscalationRecord

Separate required additional attempts from actual completed assessment attempts.

An additional attempt requirement may have multiple competency and evidence-gap targets.

An actual assessment attempt may fulfill multiple additional attempt requirements when allowed by policy.

### 7.9 Reflection and sensemaking domain

- ReflectionPrompt
- ReflectionPromptVersion
- ReflectionTriggerRule
- ReflectionTask
- ReflectionEntry
- ReflectionRevision
- ReflectionEvidenceLink
- ReflectionCompetencyLink
- ReflectionFeedbackLink
- SensemakingReview
- SensemakingReviewRevision
- SensemakingEvidenceLink
- AutomatedEvidenceSummary
- LearnerSelfAssessment

Support draft, submitted, reviewed, and revised reflection states.

Automated summaries must be stored separately from learner-authored reflections.

### 7.10 Coaching domain

- CoachingRelationship
- CoachingSession
- CoachingDialogue
- DialogueMessage
- CoachingRecommendation
- CoachingAction

### 7.11 Learning development domain

- IndividualLearningPlan
- LearningGoal
- LearningGoalRevision
- LearningGoalEvidenceLink
- LearningActivity
- LearningIntervention
- InterventionActivity
- InterventionReview
- ReassessmentPlan
- ReassessmentRequirement

### 7.12 EPA domain

- EntrustableProfessionalActivity
- EPAVersion
- EPACompetencyLink
- EPAMilestone
- EPAScope
- EPALimitation
- EPAObservation
- SupervisionScale
- SupervisionScaleVersion
- EntrustmentReview
- EntrustmentDecision

### 7.13 Progression domain

- CompetencyAttainment
- CompetencyReview
- ProgressionReview
- ProgressionDecision
- DecisionEvidenceLink
- DecisionParticipant

### 7.14 Infrastructure domain

- AuditEvent
- DomainEvent
- OutboxEvent
- BackgroundJob
- IntegrationEvent
- Notification
- NotificationPreference
- DataAccessEvent

## 8. Essential relational design requirements

Implement and document at least the following relationships:

- Institution one-to-many StudyProgram.
- StudyProgram one-to-many CompetencyFrameworkVersion through its framework.
- StudyProgram one-to-one logical AssessmentBlueprint.
- AssessmentBlueprint one-to-many AssessmentBlueprintVersion.
- CompetencyFrameworkVersion one-to-many CompetencyItem.
- CompetencyItem one-to-many CompetencyIndicator.
- CompetencyItem many-to-many BlueprintItem.
- CompetencyItem many-to-many EvidenceRequirementTemplate.
- EvidenceRequirementTemplate many-to-many eligible EvidenceSource.
- LearnerEnrollment one-to-many LearnerEvidencePlan.
- LearnerEvidencePlan one-to-many LearnerEvidenceRequirement.
- LearnerEvidenceRequirement one-to-many RequirementRevision.
- LearnerEvidenceRequirement many-to-many EvidenceRecord.
- EvidenceRecord many-to-many CompetencyItem and CompetencyIndicator.
- EvidenceEvaluation many-to-many immutable evidence revisions.
- EvidenceEvaluation one-to-many EvaluationFinding.
- EvidenceEvaluation one-to-many EvidenceGap.
- EvidenceEvaluation zero-to-many applicable PerformanceGapDecision records.
- AdaptivePlanRevision one-to-many AdditionalAttemptRequirement.
- AdditionalAttemptRequirement many-to-many EvidenceGap.
- AdditionalAttemptRequirement many-to-many eligible competency targets.
- ReflectionEntry many-to-many EvidenceRecord.
- ReflectionEntry many-to-many CompetencyItem.
- SensemakingReview many-to-many EvidenceRecord.
- PerformanceGapDecision one-to-many LearningIntervention where appropriate.
- LearningIntervention one-to-many ReassessmentRequirement.
- EPA many-to-many CompetencyItem.
- EPA one-to-many EPAObservation.
- EntrustmentDecision many-to-many supporting observations and evidence.

Use explicit through models when relationships require provenance, timestamps, contribution weights, verification, or other metadata.

Enforce database-level integrity wherever possible.

Avoid unnecessary generic foreign keys for core educational relationships.

Use normalized relational models for essential data and JSONB for configurable parameters or structured supplementary metadata.

## 9. Adaptive Evidence Engine

Implement the adaptive engine as a dedicated domain service.

Do not embed complex educational decision logic directly in Django views, templates, model save methods, or signals.

Separate the following components:

- Evidence Reconciliation Service.
- Evidence Sufficiency Evaluator.
- Performance Gap Evaluator.
- Adaptive Attempt Planner.
- Learning Intervention Planner.
- Reflection Trigger Service.
- Evidence Summary Generator.
- Decision Preparation Service.

Use deterministic, configurable, versioned rules as the initial implementation.

Do not make an LLM or other AI system the authoritative academic decision engine.

### 9.1 Required evaluation workflow

Implement logic equivalent to:

```text
ON relevant evidence event:

    identify affected learners
    identify affected competency targets
    resolve applicable academic configuration
    reconcile actual and expected evidence
    evaluate evidence sufficiency

    IF evidence is insufficient:

        classify unresolved evidence gaps
        identify eligible evidence acquisition options
        consider existing pending attempts
        calculate targeted additional requirements
        revise individual evidence plan
        supersede redundant pending requirements
        assign or request scheduling
        escalate if automatic resolution is not feasible

    ELSE:

        stop unnecessary additional evidence acquisition
        evaluate performance against applicable standards

        IF performance gap is open:

            create or update learning intervention requirements
            initiate appropriate reflection and coaching
            generate reassessment requirements
            preserve existing evidence and decisions

        ELSE:

            document performance attainment findings
            initiate appropriate reflection
            prepare competency or progression review

    persist evaluation snapshot
    persist rule versions and rationale
    publish relevant domain events
    update learner and advisor dashboards
```

### 9.2 Adaptive planning principles

The planner must optimize evidence acquisition rather than blindly increase attempt counts.

Consider:

- Unresolved evidence gaps.
- Expected informational contribution.
- Eligible assessment methods.
- Context coverage.
- Existing scheduled assessments.
- Learner burden.
- Assessor availability.
- Time constraints.
- Educational feasibility.
- Academic policy.

Do not assume that the number of required additional attempts equals the number of identified gaps.

An additional attempt may address several gaps simultaneously.

The planner must be capable of recalculating and reducing previously generated requirements.

### 9.3 Rule management

Provide configurable rules for:

- Minimum evidence requirements.
- Required competency coverage.
- Required context diversity.
- Required assessor diversity.
- Evidence verification.
- Evidence recency.
- Evidence eligibility.
- Performance standards.
- Evidence consistency.
- Decision uncertainty.
- Additional attempt selection.
- Maximum automatic adaptation.
- Escalation.
- Learning intervention.
- Reassessment.
- Reflection triggers.

Do not invent universal medical education thresholds.

Any example thresholds must be explicitly marked as demonstration configurations and must not be activated as production academic policy without approval.

Implement a safe declarative rule representation.

Never execute arbitrary Python, SQL, or JavaScript entered by academic users.

Support validation, preview, simulation, versioning, publication, and retirement of rules.

## 10. State management

Maintain separate state dimensions.

### Evidence sufficiency

- Not evaluated.
- Insufficient.
- Sufficient.
- Requires review.

### Performance gap

- Undetermined.
- Open.
- Closed.

### Evidence requirement lifecycle

- Planned.
- Active.
- Partially fulfilled.
- Fulfilled.
- Superseded.
- Cancelled.
- Escalated.

### Additional attempt lifecycle

- Required.
- Awaiting assignment.
- Assigned.
- Scheduled.
- In progress.
- Completed.
- Awaiting verification.
- Fulfilled.
- Superseded.
- Cancelled.
- Escalated.

### Learning intervention lifecycle

- Proposed.
- Required.
- Agreed.
- In progress.
- Completed.
- Awaiting reassessment.
- Reviewed.

### Formal academic decision

Maintain a separate configurable decision lifecycle.

Do not combine all these dimensions into a single learner status field.

Implement explicit state transition validation.

## 11. Reflection and sensemaking architecture

Reflection must be a first-class domain.

The learner must be able to:

- Review evidence.
- Select relevant evidence.
- Compare evidence with competency expectations.
- Examine changes over time.
- Interpret feedback.
- Identify strengths and limitations.
- Formulate explanations.
- Develop learning goals.
- Revisit previous interpretations.
- Discuss interpretations with advisors.

Automatically generated evidence summaries must support, not replace, these processes.

Provide structured and narrative reflection formats.

Support learner-initiated reflection even when no formal reflection task exists.

Support reflection privacy policies, including private drafts, advisor-shared reflections, and explicitly authorized formal review visibility.

Do not assume that all reflections should be assessed or graded.

When reflective competence is itself an academic outcome, reflection may become assessable evidence using explicit criteria.

Do not treat self-reported clinical competence as equivalent to observed clinical performance.

## 12. EPA architecture

Support Entrustable Professional Activities as an optional domain.

EPA must not be treated as another name for a competency.

An EPA is an observable unit of professional work integrating multiple competencies.

Support:

- EPA description.
- Scope of practice.
- Limitations.
- Required knowledge, skills, and attitudes.
- Core and supporting competencies.
- Risk considerations.
- Expected supervision levels.
- Stage-specific milestones.
- Workplace observations.
- Case complexity.
- Assessor identity.
- Context.
- Narrative feedback.

Undergraduate programs must be able to operate without EPA.

Professional, specialist, and subspecialist programs must be able to configure EPA-based education.

Support configurable supervision scales rather than hardcoding one universal scale.

Keep individual EPA observations separate from summative entrustment decisions.

Formal entrustment decisions must be made by authorized academic decision-makers using longitudinal evidence.

## 13. User interface requirements

Use the existing Django and Tailwind CSS foundation.

Prefer clear, responsive, accessible server-rendered interfaces.

Do not introduce a separate frontend framework without a justified architectural requirement.

### 13.1 Academic administration

Build academic and system administration as custom interfaces integrated into Titeni, with shared navigation, layouts, and UI components. Use Django views, forms, and templates for all administration workflows. Omit Django Admin from installed apps and URL configuration. Enforce applicable permissions, program scope, and audit requirements in every administrative action.

Prefer editable tables for repeatable entries with the same structure. Provide a **Tambah baris** control and place the **Aksi** column at the far right for row-level actions.

Provide interfaces for:

- Competency framework configuration.
- Competency hierarchy.
- Curriculum mapping.
- Macro assessment blueprint.
- Evidence source registry.
- Master Artifact Map.
- Expected evidence rules.
- Adaptive policies.
- Reflection prompts.
- EPA configuration.
- Academic role assignments.
- Rule simulation and publication.

### 13.2 Learner dashboard

The primary learner dashboard must answer:

1. What competencies am I expected to develop?
2. What evidence is expected?
3. What evidence have I collected?
4. What does the available evidence indicate?
5. Is the evidence sufficient?
6. Is there an identified performance gap?
7. What additional attempts are required?
8. What learning activities should I undertake?
9. What should I reflect upon?
10. How have I developed over time?

Display initial evidence requirements separately from adaptive requirements.

For each additional attempt, display why it is required and what gap it addresses.

Avoid misleading completion percentages that imply competency attainment.

### 13.3 Competency detail page

Provide a longitudinal competency-centered view containing:

- Competency definition.
- Current milestone.
- Expected performance standard.
- Expected evidence.
- Actual evidence.
- Evidence timeline.
- Evidence sufficiency.
- Performance gap status.
- Assessment trends.
- Feedback.
- Learner reflections.
- Additional attempts.
- Learning interventions.
- Reassessment.
- Formal decisions.

### 13.4 Reflection workspace

Provide an integrated workspace where learners can review evidence while composing reflections.

Support:

- Evidence selection.
- Automated evidence summaries.
- Reflection prompts.
- Narrative writing.
- Self-assessment.
- Learning goal formulation.
- Draft saving.
- Revision history.
- Coaching dialogue.

### 13.5 Advisor dashboard

Provide a longitudinal view of assigned learners.

Highlight:

- Insufficient evidence.
- Unresolved performance gaps.
- Pending additional attempts.
- Overdue activities.
- Pending reflection tasks.
- Learner concerns.
- Learning interventions.
- Reassessment needs.
- Cases requiring human review.

### 13.6 Competency committee dashboard

Provide decision-oriented evidence summaries.

Display evidence provenance, applicable standards, sufficiency findings, performance findings, historical decisions, and authorized supporting records.

Support decision rationale and approval workflows.

### 13.7 Program analytics dashboard

Provide competency coverage matrices, evidence source contributions, adaptive assessment burden, performance gap trends, and learning intervention outcomes.

Use aggregate data responsibly and protect individual confidentiality.

## 14. Authorization and privacy

Implement granular authorization using roles and academic relationships.

Potential roles include:

- System administrator.
- Institution administrator.
- Study program administrator.
- Curriculum manager.
- Assessment manager.
- Portfolio manager.
- Learner.
- Assessor.
- Clinical supervisor.
- Academic advisor.
- Coach.
- Competency committee member.
- Academic decision-maker.
- Integration service account.
- Auditor.

Do not rely on global role membership alone.

Enforce access according to institution, program, cohort, assignment, learner relationship, competency review responsibility, and record visibility.

Implement server-side authorization for every protected operation.

Prevent cross-program data leakage and enforce academic relationship and record-visibility restrictions.

Protect clinical and patient-related information.

Use de-identified clinical references wherever possible.

Do not require identifiable patient information for ordinary portfolio activities.

Implement secure file access, validation, and configurable retention policies.

Record access to sensitive records.

Do not expose private formative reflections through general administrative queries, APIs, exports, or dashboards.

## 15. Data integrity and auditability

Use PostgreSQL as the authoritative relational database.

Implement:

- Foreign key constraints.
- Unique constraints.
- Check constraints.
- Appropriate indexes.
- Transactional consistency.
- Explicit versioning.
- Immutable historical decisions.
- Evidence provenance.
- Idempotent imports.
- Duplicate prevention.
- Safe concurrent updates.
- Audit trails.

Use atomic transactions for related domain changes.

Prevent concurrent evaluations from generating duplicate additional requirements.

Use locking or equivalent concurrency controls where necessary.

Use stable idempotency keys for external events.

Implement transactional outbox patterns for reliable asynchronous processing where appropriate.

Record all academically significant changes, including:

- Configuration publication.
- Evidence verification.
- Evidence correction.
- Requirement adjustment.
- Evaluation execution.
- Rule changes.
- Decision overrides.
- Learning intervention assignment.
- Formal decisions.

Historical evaluations must remain reproducible after rules or evidence are revised.

## 16. Integration architecture

Provide a versioned integration interface for:

- Assessment systems.
- LMS platforms.
- Clinical logbooks.
- Academic information systems.
- External evidence repositories.

Support structured CSV imports where appropriate.

Use adapters to isolate external data formats from internal domain models.

External records must have stable source identifiers.

Support import validation, preview, error reporting, retries, and reconciliation.

Do not silently discard invalid records.

Do not automatically map external scores to competency attainment without approved interpretation rules.

## 17. Testing requirements

Implement automated tests covering domain services, model constraints, permissions, integration workflows, and user-facing processes.

At minimum, include the following acceptance scenarios.

### Scenario A — Initial evidence plan

Given a published competency framework and macro assessment blueprint, when a learner enters an applicable stage, the system generates the expected evidence plan automatically.

### Scenario B — Hybrid evidence

Expected evidence derived from a blueprint and manually configured sources coexist without unintended duplication.

### Scenario C — Evidence insufficient

The learner completes the initial assessment requirements, but coverage remains insufficient.

The system automatically creates targeted additional attempt requirements.

### Scenario D — Adaptive reduction

New evidence addresses multiple outstanding evidence gaps.

The system recalculates and reduces outstanding additional attempts, superseding redundant pending requirements.

### Scenario E — Sufficient evidence, closed performance gap

The system stops unnecessary additional evidence acquisition and prepares competency review.

### Scenario F — Sufficient evidence, open performance gap

The system initiates a learning intervention pathway instead of indefinitely prescribing repeated assessments.

### Scenario G — Reassessment

Following a learning intervention, reassessment evidence triggers a new sufficiency evaluation and performance gap decision.

### Scenario H — Reflection

A learner reviews several evidence records, writes a reflection, receives coaching feedback, revises the reflection, and formulates a learning goal.

The complete history remains available according to permissions.

### Scenario I — Automated summary

An automated evidence summary is clearly distinguished from learner-authored reflection.

### Scenario J — Versioning

A blueprint or rule revision does not alter historical evidence interpretations or decisions.

### Scenario K — Invalidated evidence

Previously accepted evidence is invalidated.

Affected evaluations and requirements are recalculated without deleting historical decisions.

### Scenario L — Concurrent evidence acquisition

Two relevant evidence records arrive concurrently.

The system does not create duplicate additional attempt requirements.

### Scenario M — Idempotent import

An external assessment result is imported twice.

Only one corresponding evidence record is counted.

### Scenario N — Authorization

A user cannot access learners outside authorized academic relationships.

### Scenario O — Reflection confidentiality

A private reflection is not visible to unauthorized administrators, reviewers, APIs, or exports.

### Scenario P — EPA optionality

An undergraduate program can operate without EPA.

A professional or specialist program can configure EPA observations and separate entrustment decisions.

### Scenario Q — Human escalation

When the adaptive engine cannot resolve an evidence gap within approved policies, the system escalates the case rather than creating unlimited attempts.

### Scenario R — Missing evidence

Missing evidence does not automatically produce a decision of incompetence.

### Scenario S — Evidence completion

Completed evidence requirements do not automatically produce a decision of competence.

## 18. Development roadmap

Implement the application incrementally.

### Phase 0 — Repository discovery and architecture reconciliation

Inspect the existing project.

Document:

- Existing Django applications.
- Existing models.
- Existing migrations.
- Authentication.
- Authorization.
- Templates.
- Tailwind configuration.
- PostgreSQL configuration.
- Dependency management.
- Existing tests.
- Reusable components.
- Architectural conflicts.
- Missing functionality.

Do not make destructive changes.

### Phase 1 — Academic and evidence architecture

Implement:

- Academic structures.
- Competency frameworks.
- Curriculum milestones.
- Versioning.
- Macro assessment blueprint.
- Evidence source registry.
- Master Artifact Map.
- Expected evidence requirements.
- Individual Evidence Plan.

### Phase 2 — Evidence acquisition

Implement:

- Evidence repository.
- Evidence provenance.
- Assessment attempts.
- Evidence verification.
- Evidence mapping.
- Evidence reconciliation.
- Import mechanisms.
- Integration foundations.

### Phase 3 — Adaptive engine

Implement:

- Evaluation rule management.
- Evidence sufficiency evaluation.
- Performance gap evaluation.
- Adaptive attempt planning.
- Requirement revisions.
- Automatic recalculation.
- Assignment.
- Escalation.
- Auditability.

### Phase 4 — Reflection and sensemaking

Implement:

- Automated evidence summaries.
- Reflection triggers.
- Reflection workspace.
- Artifact-level reflection.
- Competency-level sensemaking.
- Longitudinal reflection.
- Self-assessment.
- Coaching dialogue.
- Reflection confidentiality.

### Phase 5 — Learning development

Implement:

- Individual Learning Plan.
- Learning goals.
- Learning interventions.
- Remediation.
- Reassessment.
- Longitudinal review.

### Phase 6 — EPA and progression

Implement:

- EPA configuration.
- Workplace observations.
- Supervision scales.
- Entrustment reviews.
- Competency attainment.
- Formal progression decisions.

### Phase 7 — Analytics and operational hardening

Implement:

- Program analytics.
- Performance optimization.
- Security testing.
- Accessibility review.
- Backup and recovery documentation.
- Deployment documentation.
- Integration documentation.
- Operational monitoring.

Do not implement all phases as one uncontrolled code change.

Each phase must produce a working, tested, reviewable increment.

## 19. Documentation requirements

Create and maintain the following documentation within the repository:

```text
AGENTS.md
docs/
    MASTER_INSTRUCTION.md
    PRODUCT_VISION.md
    EDUCATIONAL_CONCEPTS.md
    BUSINESS_PROCESSES.md
    BUSINESS_RULES.md
    ARCHITECTURE.md
    DOMAIN_MODEL.md
    DATABASE_SCHEMA.md
    ERD.md
    STATE_TRANSITIONS.md
    ADAPTIVE_ENGINE.md
    REFLECTION_AND_SENSEMAKING.md
    AUTHORIZATION.md
    INTEGRATION_SPECIFICATION.md
    TESTING_STRATEGY.md
    IMPLEMENTATION_ROADMAP.md
    DEVELOPMENT_LOG.md
    DECISIONS.md
    OPEN_QUESTIONS.md
```

Store this master instruction in `docs/MASTER_INSTRUCTION.md`.

Use `AGENTS.md` as a concise persistent instruction for future Codex sessions.

Instruct future agents to read the master instruction and relevant domain documentation before making architectural changes.

Maintain Architecture Decision Records for consequential technical and educational design decisions.

Keep documentation synchronized with implemented functionality.

Generate Mermaid ERDs, process diagrams, and state diagrams where appropriate.

## 20. Coding and engineering standards

Follow the existing project conventions where reasonable.

Use:

- Django ORM.
- Django migrations.
- Django forms and validation.
- Django authentication foundations.
- Explicit domain services.
- Type annotations where useful.
- Clear domain naming.
- Automated tests.
- Structured logging.
- Secure configuration through environment variables.

Maintain cross-platform compatibility across macOS, Linux, and Windows where supported by the project dependencies.

Do not introduce unnecessary operating-system-specific assumptions.

Use uv for dependency management.

Preserve the existing Python and Django version strategy unless inspection identifies a justified need for change.

Do not commit credentials, secret keys, database passwords, or sensitive learner data.

Do not modify production databases.

Do not run destructive migrations or delete existing data without explicit approval.

Use reversible migrations where practical.

Separate schema migrations from complex data migrations where appropriate.

Use synthetic demonstration data only.

## 21. Definition of done

A feature is complete only when:

- Its educational purpose is documented.
- Its business rules are implemented.
- Its database constraints are appropriate.
- Its authorization is enforced.
- Its audit requirements are satisfied.
- Its user interface is usable.
- Its state transitions are validated.
- Its automated tests pass.
- Its documentation is updated.
- Existing functionality remains operational.
- Relevant assumptions and limitations are disclosed.

## 22. Immediate execution instructions

Start with Phase 0.

Perform the following actions in order:

1. Inspect the existing Titeni repository.
2. Identify existing architecture and reusable components.
3. Save this instruction as `docs/MASTER_INSTRUCTION.md`.
4. Create or update `AGENTS.md`.
5. Produce a gap analysis comparing the existing application with this specification.
6. Produce the proposed Django domain module structure.
7. Produce the complete logical data model.
8. Produce the proposed ERD with cardinalities.
9. Produce the detailed business process documentation.
10. Produce the business rule catalogue.
11. Produce the adaptive engine specification.
12. Produce the reflection and sensemaking specification.
13. Produce the authorization architecture.
14. Produce a phased implementation backlog.
15. Identify unresolved educational policies requiring human decisions.
16. Implement Phase 1 after the foundational architecture is coherent.
17. Run applicable Django checks and automated tests.
18. Update the development log.
19. Report completed work, modified files, test results, architectural decisions, limitations, and remaining tasks.

Do not stop at generic recommendations or pseudocode when implementation is feasible.

Make concrete repository changes.

However, do not invent consequential academic policies merely to complete implementation.

Where a policy is unresolved, implement a configurable mechanism, document the unresolved decision, and use explicitly labeled demonstration configurations for testing.

Request human clarification when a decision would materially alter educational semantics, data integrity, privacy, or high-stakes academic outcomes.

The central requirement must remain intact throughout development:

**Titeni continuously acquires, interprets, and adapts evidence requirements; supports reflective sensemaking and learning development; and facilitates defensible decisions about whether performance gaps have been closed.**

Begin now.
